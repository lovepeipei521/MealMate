from scripts.howtocook_loader import HowToCookLoader, ParsedDocument


def make_document() -> ParsedDocument:
    return ParsedDocument(
        doc_id="00000000-0000-0000-0000-000000000001",
        dish_name="番茄炒蛋",
        category="素菜",
        difficulty="简单",
        data_source="recipes",
        source_type="recipes",
        source="dishes/vegetable_dish/番茄炒蛋.md",
        is_dish_index=False,
        content="# 番茄炒蛋\n\n## 步骤\n\n1. 翻炒。",
    )


def test_global_document_uses_null_database_user_id():
    document = make_document()

    assert document.to_dict()["user_id"] is None


def test_global_chunks_use_global_metadata_and_parent_id():
    document = make_document()
    chunks = HowToCookLoader(data_path=".").create_chunks([document])

    assert chunks
    assert chunks[0].metadata["user_id"] == "GLOBAL"
    assert chunks[0].metadata["parent_id"] == document.doc_id
