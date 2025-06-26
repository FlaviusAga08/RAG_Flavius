import os
from pathlib import Path
import fitz
import textract
import asyncio
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_chroma import Chroma
from domain.models import QueryResponse
from dotenv import load_dotenv

try:
    from langchain_community.document_loaders import UnstructuredExcelLoader, UnstructuredFileLoader
    excel_supported = True
except ImportError:
    excel_supported = False


class DocumentIndexer:
    def __init__(self, doc_location: str, persist_directory: str, api_key: str):
        self.doc_location = doc_location
        self.persist_directory = persist_directory
        self.embedding = OpenAIEmbeddings(openai_api_key=api_key)
        self.llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, openai_api_key=api_key)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.vectordb = None
        self.qa_chain = None

    def load_vector_db(self):
        if not Path(self.persist_directory).exists():
            print("Persist directory not found.")
            return

        self.vectordb = Chroma(persist_directory=self.persist_directory, embedding_function=self.embedding)
        retriever = self.vectordb.as_retriever(search_kwargs={"k": 5})
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )
        print("Vector DB loaded.")

    def _index_pdf(self, filename: str, file_path: str):
        doc = fitz.open(file_path)
        for i in range(doc.page_count):
            page = doc.load_page(i)
            page_doc = Document(page_content=page.get_text(), metadata={"source": filename, "page": i})
            chunks = self.splitter.split_documents([page_doc])
            for chunk in chunks:
                chunk.metadata["source"] = filename
            self.vectordb.add_documents(chunks)

    def _index_docx(self, filename: str, file_path: str):
        text = textract.process(file_path).decode("utf-8")
        if text:
            docs = [Document(page_content=text, metadata={"source": filename})]
            chunks = self.splitter.split_documents(docs)
            self.vectordb.add_documents(chunks)

    def _index_xlsx(self, filename: str, file_path: str):
        if not excel_supported:
            print("Excel support is not available.")
            return
        docs = UnstructuredExcelLoader(file_path).load()
        for doc in docs:
            doc.metadata["source"] = filename
        chunks = self.splitter.split_documents(docs)
        self.vectordb.add_documents(chunks)

    def _index_text_files(self, filename: str, file_path: str):
        docs = UnstructuredFileLoader(file_path).load()
        for doc in docs:
            doc.metadata["source"] = filename
        chunks = self.splitter.split_documents(docs)
        self.vectordb.add_documents(chunks)

    def _index_all_documents_sync(self):
        """Sync internal helper for indexing all docs."""
        self.vectordb = Chroma(persist_directory=self.persist_directory, embedding_function=self.embedding)
        files_indexed = 0

        for path in Path(self.doc_location).rglob("*"):
            if not path.is_file():
                continue
            filename = path.name
            file_path = str(path)

            try:
                ext = filename.lower()
                dispatch = {
                    ext.endswith(".pdf"): self._index_pdf,
                    ext.endswith((".doc", ".docx")): self._index_docx,
                    ext.endswith(".xlsx") and excel_supported: self._index_xlsx,
                    ext.endswith((".txt", ".md", ".rtf")): self._index_text_files,
                }

                for condition, func in dispatch.items():
                    if condition:
                        func(filename, file_path)
                        print(f"Indexed file: {filename}")
                        break
                else:
                    continue

                files_indexed += 1

            except Exception as e:
                print(f"Error indexing {filename}: {e}")

        if files_indexed > 0:
            retriever = self.vectordb.as_retriever(search_kwargs={"k": 5})
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True
            )
            print(f"Indexing complete. Total files indexed: {files_indexed}")

    async def index_documents(self):
        """Async wrapper for indexing to keep async chain intact."""
        await asyncio.to_thread(self._index_all_documents_sync)

    async def query(self, query_str: str, top_k: int = 5) -> list[QueryResponse]:
        if self.qa_chain is None:
            raise RuntimeError("Vector DB not loaded.")

        # Update search param
        self.qa_chain.retriever.search_kwargs["k"] = top_k

        # Run query on threadpool to avoid blocking event loop
        response = await asyncio.to_thread(self.qa_chain.invoke, query_str)

        raw_sources = response.get("source_documents", [])
        seen = set()
        sources = []

        for doc in raw_sources:
            filename = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page")
            suffix = f" - page {page + 1}" if isinstance(page, int) else ""

            source_entry = f"{filename}{suffix}"
            if source_entry not in seen:
                seen.add(source_entry)
                sources.append(source_entry)

        return [QueryResponse(result=response["result"], sources=sources)]