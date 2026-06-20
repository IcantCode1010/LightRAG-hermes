from hermes_ui.document_router import route_document_query


def test_general_chat_routes_to_hermes():
    route = route_document_query("hi", {"documents": []}, {})

    assert route.intent == "general"
    assert route.document_keys == []


def test_broad_document_question_routes_to_latest_all():
    route = route_document_query(
        "Summarize all indexed manuals",
        {
            "documents": [
                {
                    "document_key": "boeing-manual",
                    "latest_version_label": "2026-06-20-001",
                }
            ]
        },
        {},
    )

    assert route.intent == "latest_all"
    assert route.document_keys == []


def test_specific_document_question_selects_matching_document():
    route = route_document_query(
        "What does the boeing b737 manual say about takeoff?",
        {
            "documents": [
                {
                    "document_key": "boeing-b737-700-800-900-operations-manual",
                    "latest_version_label": "2026-06-20-001",
                },
                {
                    "document_key": "15-flight-controls",
                    "latest_version_label": "2026-06-20-001",
                },
            ]
        },
        {},
    )

    assert route.intent == "latest_documents"
    assert route.document_keys == ["boeing-b737-700-800-900-operations-manual"]


def test_ambiguous_document_question_uses_latest_all():
    route = route_document_query(
        "Compare the manuals",
        {
            "documents": [
                {
                    "document_key": "boeing-b737-700-800-900-operations-manual",
                    "latest_version_label": "2026-06-20-001",
                },
                {
                    "document_key": "airbus-maintenance-training-student-book",
                    "latest_version_label": "2026-06-20-001",
                },
            ]
        },
        {},
    )

    assert route.intent == "latest_all"
    assert route.document_keys == []


def test_unsearchable_document_is_not_selected_from_active_snapshot():
    route = route_document_query(
        "Summarize the airbus student book",
        {
            "documents": [
                {
                    "document_key": "airbus-maintenance-training-student-book",
                    "latest_version_label": "2026-06-20-001",
                }
            ]
        },
        {
            "active_snapshot": {
                "latest_versions": {
                    "boeing-b737-700-800-900-operations-manual": "2026-06-20-001"
                }
            }
        },
    )

    assert route.intent == "latest_all"
    assert route.document_keys == []
