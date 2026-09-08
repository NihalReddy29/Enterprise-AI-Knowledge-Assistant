"""
Re-index all INDEXED documents from the database into ChromaDB with Gemini embeddings.
Run this after switching embedding providers or clearing the vector store.
"""
import sys, logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

from app.database.session import SessionLocal
from app.models.user import Document, DocumentStatus
from app.services.document_processor import get_document_processor
from app.services.storage import get_storage_backend
from app.services.indexing import get_indexing_service

def reindex_all():
    indexing = get_indexing_service()
    processor = get_document_processor()
    storage   = get_storage_backend()

    with SessionLocal() as db:
        docs = (
            db.query(Document)
            .filter(
                Document.status == DocumentStatus.INDEXED,
                Document.extracted_text_path.isnot(None),
            )
            .all()
        )

    if not docs:
        print("No INDEXED documents found in the database.")
        print("Upload a document via the UI first, then run this script.")
        return

    print(f"Found {len(docs)} document(s) to re-index with Gemini embeddings.\n")

    success = 0
    for doc in docs:
        try:
            print(f"[{doc.id}] {doc.filename} (owner={doc.owner_id})")
            result = processor.load_extraction_result(storage, doc.extracted_text_path)
            idx_result = indexing.index_document(
                result=result,
                document_id=doc.id,
                filename=doc.filename,
                owner_id=doc.owner_id,
                org_id=doc.org_id,
            )
            print(f"      ✓ {idx_result.chunk_count} chunks indexed via {idx_result.embedding_provider}\n")
            success += 1
        except Exception as e:
            logger.error("Failed to re-index doc %d (%s): %s", doc.id, doc.filename, e)

    total = indexing.vector_store.count()
    print(f"\nDone: {success}/{len(docs)} documents re-indexed.")
    print(f"ChromaDB now contains {total} total vectors.")

if __name__ == "__main__":
    reindex_all()
