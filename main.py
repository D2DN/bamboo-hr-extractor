#!/usr/bin/env python3
import click
from bamboo_extractor.config import Config
from bamboo_extractor.client import BambooHRClient
from bamboo_extractor.exporter import export
from bamboo_extractor.downloader import download_resumes, enrich_with_file_paths


@click.group()
def cli():
    """BambooHR candidate data extractor."""


@cli.command()
@click.option("--api-key", envvar="BAMBOO_API_KEY", help="BambooHR API key")
@click.option("--domain", envvar="BAMBOO_COMPANY_DOMAIN", help="Company subdomain (e.g. mycompany)")
@click.option("--status", envvar="BAMBOO_APPLICATION_STATUS", default="ALL",
              type=click.Choice(["NEW", "ACTIVE", "INACTIVE", "HIRED", "ALL", "ALL_ACTIVE"], case_sensitive=False),
              help="Filter by application status group")
@click.option("--job-id", envvar="BAMBOO_JOB_ID", default=None, type=int, help="Filter by job ID")
@click.option("--new-since", envvar="BAMBOO_NEW_SINCE", default=None,
              help="Filter applications created after this date (YYYY-MM-DD HH:MM:SS)")
@click.option("--format", "output_format", envvar="BAMBOO_OUTPUT_FORMAT", default="csv",
              type=click.Choice(["csv", "json"], case_sensitive=False), help="Output format")
@click.option("--output", "output_file", envvar="BAMBOO_OUTPUT_FILE", default="candidates_export",
              help="Output filename (without extension)")
@click.option("--resumes-dir", envvar="BAMBOO_RESUMES_DIR", default=None,
              help="Directory to save downloaded CVs/resumes (skipped if not set)")
@click.option("--job-title", envvar="BAMBOO_JOB_TITLE", default=None,
              help="Filter by job title (partial match, case-insensitive). Overrides --job-id.")
@click.option("--demo", is_flag=True, default=False, help="Demo mode: limit to 10 candidates")
def extract(api_key, domain, status, job_id, new_since, output_format, output_file, resumes_dir, job_title, demo):
    """Extract candidate applications from BambooHR ATS and optionally download CVs."""
    config = Config(
        api_key=api_key or "",
        company_domain=domain or "",
        application_status=status,
        job_id=str(job_id) if job_id else None,
        job_title=job_title,
        new_since=new_since,
        output_format=output_format.lower(),
        output_file=output_file,
        resumes_dir=resumes_dir,
    )

    try:
        config.validate()
    except ValueError as e:
        raise click.UsageError(str(e))

    client = BambooHRClient(config)

    click.echo(f"Fetching applications from {config.base_url} ...")
    try:
        if job_title:
            job_ids = client.get_job_ids_by_title(job_title)
            if not job_ids:
                raise click.ClickException(f"No jobs found matching '{job_title}'. Use 'list-jobs' to see available jobs.")
            click.echo(f"Matched {len(job_ids)} job(s) for '{job_title}': {job_ids}")
            applications = []
            for jid in job_ids:
                config.job_id = str(jid)
                applications.extend(client.get_all_applications())
        else:
            applications = client.get_all_applications()
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"API error: {e}")

    if demo:
        applications = applications[:10]
        click.echo(f"Demo mode: limited to {len(applications)} application(s).")
    else:
        click.echo(f"Retrieved {len(applications)} application(s).")

    # Export d'abord sans les chemins de CV
    path = export(applications, output_format.lower(), output_file)
    click.echo(f"Exported to {path}")

    if resumes_dir:
        click.echo(f"\nDownloading CVs to '{resumes_dir}' ...")
        stats, file_map = download_resumes(
            client=client,
            applications=applications,
            resumes_dir=resumes_dir,
        )
        click.echo(
            f"Done: {stats['downloaded']} downloaded, "
            f"{stats['skipped']} skipped, {stats['errors']} error(s)."
        )
        # Mise à jour du fichier d'export avec les chemins de CV
        enriched = enrich_with_file_paths(applications, file_map)
        export(enriched, output_format.lower(), output_file)
        click.echo(f"Export updated with CV paths → {path}")


@cli.command()
@click.option("--api-key", envvar="BAMBOO_API_KEY", required=True, help="BambooHR API key")
@click.option("--domain", envvar="BAMBOO_COMPANY_DOMAIN", required=True, help="Company subdomain")
def list_jobs(api_key, domain):
    """List all available jobs."""
    config = Config(api_key=api_key, company_domain=domain)
    client = BambooHRClient(config)
    try:
        jobs = client.get_jobs()
        for j in jobs:
            title = j.get("title", {})
            label = title.get("label") if isinstance(title, dict) else title
            click.echo(f"  [{j.get('id')}] {label}")
    except Exception as e:
        raise click.ClickException(f"API error: {e}")


@cli.command()
@click.option("--api-key", envvar="BAMBOO_API_KEY", required=True)
@click.option("--domain", envvar="BAMBOO_COMPANY_DOMAIN", required=True)
def debug(api_key, domain):
    """Print raw API response for the first application to inspect field structure."""
    import json
    config = Config(api_key=api_key, company_domain=domain)
    client = BambooHRClient(config)

    data = client.get_applications(page=1, application_status="ALL")
    apps = data.get("applications", [])
    if not apps:
        click.echo("No applications found.")
        return

    first = apps[0]
    app_id = first.get("id")
    click.echo("=== application list (first item) ===")
    click.echo(json.dumps(first, indent=2))

    click.echo(f"\n=== application details (id={app_id}) ===")
    details = client.get_application_details(app_id)
    click.echo(json.dumps(details, indent=2))

    resume_file_id = details.get("resumeFileId") or first.get("resumeFileId")
    if resume_file_id:
        click.echo(f"\n=== download attempt (resumeFileId={resume_file_id}) ===")
        import requests as req
        from requests.auth import HTTPBasicAuth
        url = f"https://{domain}.bamboohr.com/files/download.php?id={resume_file_id}"
        resp = req.get(url, auth=HTTPBasicAuth(api_key, "x"))
        click.echo(f"URL: {url}")
        click.echo(f"Status: {resp.status_code}")
        click.echo(f"Content-Type: {resp.headers.get('Content-Type')}")
        click.echo(f"Content-Disposition: {resp.headers.get('Content-Disposition')}")
        click.echo(f"First 200 bytes: {resp.content[:200]}")
    else:
        click.echo("\nNo resumeFileId found in this application.")


if __name__ == "__main__":
    cli()
