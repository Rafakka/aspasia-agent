
import logging

from concurrent.futures import ThreadPoolExecutor, as_completed

from research_agent import config

from research_agent.state import AcquiredResource, SearchResult

from research_agent.toolkit import filters

from research_agent.ingestion.acquisition import (
    AcquisitionError,
    AcquisitionOptions,
    AcquisitionResult,
    AcquisitionStatus,
    acquire_resource,
)

log = logging.getLogger(__name__)

def _get_resource_urls(
    discoveries: list[SearchResult],
    acquisition: AcquisitionResult,
) -> set[str]:
    urls = {
        discovery.url
        for discovery in discoveries
    }

    urls.update(
        url
        for url in (
            acquisition.original_url,
            acquisition.final_url,
            acquisition.resource.url if acquisition.resource else None,
        )
        if url is not None
    )

    return {
        filters.normalize_source_url(url)
        for url in urls
    }

def should_retry_acquisition(
    acquisition: AcquisitionResult,
) -> bool:
    """Determine whether an acquisition result is eligible for retry."""

    if acquisition.extracted_content:
        return False

    if acquisition.error is None:
        return False

    retryable_errors = {
        "DOWNLOAD_FAILED",
        "EMPTY_RESOURCE",
        "EXTRACTION_FAILED",
        "UNEXPECTED_ACQUISITION_ERROR",
    }

    return acquisition.error.code in retryable_errors

def _prepare_acquisition_jobs(
        search_results:list[SearchResult],
        accumulated_resources:list[AcquiredResource],
        ) -> tuple[list[dict], list[AcquiredResource]]:

    identity_to_index: dict[str, int] = {}

    for index, item in enumerate(accumulated_resources):
        identities = _get_resource_urls(
            item.discoveries,
            item.acquisition,
        )

        for identity in identities:
            identity_to_index[identity] = index

    processed_this_round = {}
    processed_indices: set[int] = set()
    discoveries_by_index: dict[int, list[SearchResult]] = {}
    updated_discovery_indices: set[int] = set()
    jobs = []

    # 1. Build acquisition jobs
    for position, result in enumerate(search_results):
        identity = filters.normalize_source_url(result.url)

        # This identity was already encountered this round.
        if identity in processed_this_round:
            target_type, target_index = processed_this_round[identity]

            if target_type == "existing":
                discoveries = discoveries_by_index[target_index]
            else:
                discoveries = jobs[target_index]["discoveries"]

            if result not in discoveries:
                discoveries.append(result)

                if target_type == "existing":
                    updated_discovery_indices.add(target_index)

            continue

        existing_index = identity_to_index.get(identity)

        if existing_index is not None:
            previous_resource = accumulated_resources[existing_index]

            discoveries = discoveries_by_index.setdefault(
                existing_index,
                list(previous_resource.discoveries),
            )

            if result not in discoveries:
                discoveries.append(result)
                updated_discovery_indices.add(existing_index)

            processed_this_round[identity] = (
                "existing",
                existing_index,
            )

            # Another URL may identify the same existing resource.
            if existing_index in processed_indices:
                continue

            processed_indices.add(existing_index)

            if (
                previous_resource.attempt_count
                >= config.MAX_ACQUISITION_ATTEMPTS
                or not should_retry_acquisition(
                    previous_resource.acquisition
                )
            ):
                log.info(
                    "fetch: skipping previously acquired source %s",
                    result.url,
                )
                continue

            attempt_count = previous_resource.attempt_count + 1

        else:
            attempt_count = 1
            discoveries = [result]

        jobs.append(
            {
                "position": position,
                "result": result,
                "attempt_count": attempt_count,
                "existing_index": existing_index,
                "discoveries": discoveries,
            }
        )

        if existing_index is None:
            processed_this_round[identity] = (
                "job",
                len(jobs) - 1,
            )

    for index in updated_discovery_indices:
        previous_resource = accumulated_resources[index]

        accumulated_resources[index] = previous_resource.model_copy(
            update={"discoveries": discoveries_by_index[index]}
        )

    return jobs, accumulated_resources

def _execute_acquisition_jobs(
    jobs: list[dict],
    options: AcquisitionOptions,
) -> dict[int, tuple[AcquiredResource, int | None]]:

    # Execute acquisitions concurrently amd collet their results

    completed_results = {}

    with ThreadPoolExecutor(
        max_workers=config.MAX_CONCURRENT_ACQUISITIONS
    ) as executor:

        future_to_job = {
            executor.submit(
                acquire_resource,
                search_result=job["result"],
                options=options,
            ): job
            for job in jobs
        }

        for future in as_completed(future_to_job):
            job = future_to_job[future]

            try:
                acquisition = future.result()

            except Exception as exc:
                log.exception(
                    "Unexpected acquisition error for %s",
                    job["result"].url,
                )

                acquisition = AcquisitionResult(
                    status=AcquisitionStatus.FAILED,
                    error=AcquisitionError(
                        code="UNEXPECTED_ACQUISITION_ERROR",
                        message=str(exc),
                    ),
                )

            resource_record = AcquiredResource(
                discoveries=job["discoveries"],
                acquisition=acquisition,
                attempt_count=job["attempt_count"],
            )

            completed_results[job["position"]] = (
                resource_record,
                job["existing_index"],
            )

            log.info(
                "fetch: %s -> %s (attempt %d)",
                job["result"].url,
                acquisition.status.value,
                job["attempt_count"],
            )

    return completed_results

def _consolidate_acquisition_results(
    completed_results: dict[int, tuple[AcquiredResource, int | None]],
    accumulated_resources: list[AcquiredResource],
) -> list[AcquiredResource]:

    acquired_this_round = 0

    for position in sorted(completed_results):
        resource_record, existing_index = completed_results[position]

        if existing_index is not None:
            accumulated_resources[existing_index] = resource_record
        else:
            accumulated_resources.append(resource_record)

        acquired_this_round += 1

    log.info(
        "fetch: processed %d acquisitions; %d total resources",
        acquired_this_round,
        len(accumulated_resources),
    )

    return accumulated_resources


def fetch_resources(
        search_results: list[SearchResult],
        acquired_resources: list[AcquiredResource],
        ) -> list[AcquiredResource]:

    accumulated_resources = list(acquired_resources)

    jobs, accumulated_resources = _prepare_acquisition_jobs(
            search_results,
            accumulated_resources,
        )

    options = AcquisitionOptions(
            store_original=True,
            extract_content=True,
            )


    completed_results = _execute_acquisition_jobs(jobs, options)

    return _consolidate_acquisition_results(
            completed_results,
            accumulated_resources,
            )
