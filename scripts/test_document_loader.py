from src.services.document_loader import load_all_documents


def main():
    documents = load_all_documents()

    print(f"Documents loaded: {len(documents)}")

    for document in documents:
        print("\n" + "=" * 60)
        print(f"Title: {document['title']}")
        print(f"Source: {document['source']}")
        print(f"Filename: {document['filename']}")
        print(f"Extracted characters: {len(document['text'])}")
        print(f"Preview:\n{document['text'][:500]}")


if __name__ == "__main__":
    main()
