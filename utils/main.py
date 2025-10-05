# Standard library
import sys
import time

# Local imports
try:
    from import_python_official import main as official_updater
    from import_python_organizers import main as organizer_updater
    from logging_config import get_tqdm_logger
    from sort_yaml import sort_data
except ImportError:
    from .import_python_official import main as official_updater
    from .import_python_organizers import main as organizer_updater
    from .logging_config import get_tqdm_logger
    from .sort_yaml import sort_data


def main() -> None:
    """Main data processing pipeline with comprehensive logging."""
    logger = get_tqdm_logger(__name__)

    logger.info("🚀 Starting Python Deadlines data processing pipeline")
    start_time = time.time()

    try:
        # Step 1: Import from Python official calendar
        logger.info("📅 Step 1: Importing from Python official calendar")
        step_start = time.time()
        official_updater()
        logger.info(f"✅ Official calendar import completed in {time.time() - step_start:.2f}s")

        # Step 2: Sort and validate data
        logger.info("🔄 Step 2: Sorting and validating data")
        step_start = time.time()
        sort_data(skip_links=True)
        logger.info(f"✅ Data sorting completed in {time.time() - step_start:.2f}s")

        # Step 3: Import from Python organizers
        logger.info("👥 Step 3: Importing from Python organizers")
        step_start = time.time()
        organizer_updater()
        logger.info(f"✅ Organizers import completed in {time.time() - step_start:.2f}s")

        # Step 4: Final sort and validation
        logger.info("🔄 Step 4: Final sorting and validation")
        step_start = time.time()
        sort_data(skip_links=True)
        logger.info(f"✅ Final sorting completed in {time.time() - step_start:.2f}s")

        total_time = time.time() - start_time
        logger.info(f"🎉 Data processing pipeline completed successfully in {total_time:.2f}s")

    except Exception as e:
        logger.error(f"❌ Pipeline failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
