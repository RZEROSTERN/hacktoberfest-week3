from app.notes import (
    GROUPS,
    Line,
    NoteItem,
    Notes,
    check_notes,
    chunk_lines,
    format_chunk,
    has_substance,
    merge_notes,
    repair_notes,
)


def empty_notes(**fields: object) -> Notes:
    base: dict[str, object] = {
        "client": "",
        "client_context": [],
        "problem": [],
        "goals": [],
        "requirements": [],
        "constraints": [],
        "budget": [],
        "deadlines": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
    }
    base.update(fields)
    return Notes.model_validate(base)


def test_every_group_of_sourced_items_is_covered() -> None:
    assert set(GROUPS) == {
        "client_context", "problem", "goals", "requirements", "constraints",
        "budget", "deadlines", "next_steps", "risks",
    }  # fmt: skip


def test_next_steps_survive_check_repair_and_merge() -> None:
    a = empty_notes(
        next_steps=[
            NoteItem(text="Enviar prototipo", segment_ids=[3]),
            NoteItem(text="Sin fuente", segment_ids=[]),
        ]
    )
    assert len(check_notes(a, {3})) == 1
    fixed, dropped = repair_notes(a, {3})
    assert [i.text for i in fixed.next_steps] == ["Enviar prototipo"] and dropped == 1
    b = empty_notes(next_steps=[NoteItem(text="enviar prototipo", segment_ids=[40])])
    assert merge_notes([fixed, b]).next_steps[0].segment_ids == [3, 40]


def test_chunks_split_by_time_on_segment_boundaries() -> None:
    lines = [Line(i, i * 100.0, f"t{i}") for i in range(12)]  # one segment every 100 s
    chunks = chunk_lines(lines, seconds=480)
    assert [len(c) for c in chunks] == [5, 5, 2]
    assert [line.idx for c in chunks for line in c] == list(range(12))  # nothing lost or repeated


def test_a_short_call_is_one_chunk() -> None:
    assert len(chunk_lines([Line(0, 0.0, "a"), Line(1, 30.0, "b")])) == 1
    assert chunk_lines([]) == []


def test_chunk_text_shows_the_global_segment_id_and_time() -> None:
    assert format_chunk([Line(41, 125.4, "hola")]) == "[S41 @ 125s] hola"


def test_check_flags_unsourced_and_unknown_ids() -> None:
    notes = empty_notes(
        requirements=[
            NoteItem(text="ok", segment_ids=[3]),
            NoteItem(text="no source", segment_ids=[]),
            NoteItem(text="made up id", segment_ids=[3, 99]),
        ]
    )
    problems = check_notes(notes, {3, 4})
    assert len(problems) == 2
    assert not any(p.hard for p in problems)


def test_repair_keeps_valid_sources_and_drops_the_rest() -> None:
    notes = empty_notes(
        requirements=[
            NoteItem(text="ok", segment_ids=[3]),
            NoteItem(text="no source", segment_ids=[]),
            NoteItem(text="partly valid", segment_ids=[3, 99]),
            NoteItem(text="only invalid", segment_ids=[99]),
            NoteItem(text="  ", segment_ids=[3]),
        ]
    )
    fixed, dropped = repair_notes(notes, {3, 4})
    assert [i.text for i in fixed.requirements] == ["ok", "partly valid"]
    assert fixed.requirements[1].segment_ids == [3]
    assert dropped == 3
    assert len(notes.requirements) == 5  # the original is untouched


def test_merge_joins_repeated_items_and_their_sources() -> None:
    a = empty_notes(
        client="",
        requirements=[NoteItem(text="Reservas en línea.", segment_ids=[1])],
        open_questions=["¿Fotos?"],
    )
    b = empty_notes(
        client="Kevin",
        requirements=[
            NoteItem(text="reservas en línea", segment_ids=[40]),
            NoteItem(text="Galería", segment_ids=[41]),
        ],
        open_questions=["¿fotos?", "¿Logo?"],
    )
    merged = merge_notes([a, b])
    assert merged.client == "Kevin"
    assert [(i.text, i.segment_ids) for i in merged.requirements] == [
        ("Reservas en línea.", [1, 40]),
        ("Galería", [41]),
    ]
    assert merged.open_questions == ["¿Fotos?", "¿Logo?"]


def test_has_substance() -> None:
    assert not has_substance(empty_notes())
    assert not has_substance(empty_notes(client_context=[NoteItem(text="x", segment_ids=[1])]))
    assert has_substance(empty_notes(problem=[NoteItem(text="x", segment_ids=[1])]))
