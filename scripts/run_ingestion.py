"""Synchronize the global HowToCook dataset into PostgreSQL and Milvus.

Run from the repository root after ``python -m scripts.sync_data``:

    python -m scripts.run_ingestion
"""

import asyncio
import logging
from pathlib import Path

from app.config import settings
from app.database.document_repository import document_repository
from app.database.session import close_db, init_db
from app.rag.embeddings.embedding_factory import get_embedding_model
from app.rag.vector_stores.vector_store_factory import get_vector_store
from scripts.howtocook_loader import HowToCookLoader

logger = logging.getLogger(__name__)

GLOBAL_DATA_SOURCE = "recipes"


async def run_ingestion() -> int:
    """Load HowToCook documents and rebuild the global recipe indexes."""
    howtocook = settings.rag.data_source.howtocook
    base_path = Path(settings.rag.paths.base_data_path)
    dishes_path = base_path / howtocook.path_suffix
    tips_path = base_path / howtocook.tips_path_suffix

    if not dishes_path.is_dir():
        raise FileNotFoundError(
            f"HowToCook data directory not found: {dishes_path}. "
            "Run `python -m scripts.sync_data` first."
        )

    headers = [tuple(item) for item in howtocook.headers_to_split_on]
    loader = HowToCookLoader(
        data_path=str(dishes_path),
        tips_path=str(tips_path),
        headers_to_split_on=headers,
    )

    logger.info("Loading global HowToCook documents from %s", dishes_path)
    documents = loader.load_documents()
    if not documents:
        raise RuntimeError(
            f"No HowToCook documents found under {dishes_path}. "
            "Check the synchronized dataset."
        )

    logger.info("Creating vector chunks for %d documents", len(documents))
    chunks = loader.create_chunks(documents)
    if not chunks:
        raise RuntimeError("HowToCook loader produced no vector chunks.")

    await init_db()
    try:
        deleted = await document_repository.delete_by_data_source(GLOBAL_DATA_SOURCE)
        logger.info("Removed %d previous global documents", deleted)

        created = await document_repository.create_batch(
            [document.to_dict() for document in documents]
        )
        logger.info("Stored %d global documents in PostgreSQL", len(created))

        embeddings = get_embedding_model(settings.rag)
        collection_names = settings.rag.vector_store.collection_names
        recipes_collection = collection_names["recipes"]

        logger.info(
            "Rebuilding Milvus collection %s with %d chunks",
            recipes_collection,
            len(chunks),
        )
        get_vector_store(
            milvus_config=settings.database.milvus,
            collection_name=recipes_collection,
            embeddings=embeddings,
            chunks=chunks,
            force_rebuild=True,
        )

        stored_count = await document_repository.count_by_data_source(
            GLOBAL_DATA_SOURCE
        )
        print(f"Global documents in PostgreSQL: {stored_count}")
        print(f"Vector chunks in {recipes_collection}: {len(chunks)}")
        return 0
    finally:
        await close_db()


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        return asyncio.run(run_ingestion())
    except Exception:
        logger.exception("HowToCook ingestion failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
