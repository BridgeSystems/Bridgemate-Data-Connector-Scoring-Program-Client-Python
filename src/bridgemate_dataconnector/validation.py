"""Client-side validation for the outgoing DTOs.

These functions are hand-written ports of the ``Validate()`` methods on the .NET reference
client's SharedDTO classes. They produce exactly the same boolean result and the same
validation-message strings (text and order) as the C# originals; the parity is asserted by
``tests/test_validation_fixtures.py`` against golden fixtures generated with the .NET client.

Each validator assigns the collected messages to ``dto.validation_messages`` and returns
``True`` when the DTO is valid. The message texts use the C# PascalCase property names (the
wire names), not the Python snake_case field names, and deliberately preserve the reference
implementation's typos and formatting quirks: do not "fix" them, they are part of the parity
contract.
"""

from __future__ import annotations

import os
import re
from datetime import date
from enum import IntEnum

from .dto import (
    Bridgemate2SettingsDTO,
    Bridgemate3SettingsDTO,
    BridgemateSettingsDTO,
    ContinueDTO,
    HandrecordDTO,
    InitDTO,
    ParticipationDTO,
    PlayerDataDTO,
    ResultDTO,
    RoundDTO,
    ScoringGroupDTO,
    SectionDTO,
    SectionUpdateDTO,
    SessionDTO,
    TableDTO,
    TdCallDTO,
)

__all__ = [
    "validate_bridgemate2_settings_dto",
    "validate_bridgemate3_settings_dto",
    "validate_continue_dto",
    "validate_handrecord_dto",
    "validate_init_dto",
    "validate_participation_dto",
    "validate_player_data_dto",
    "validate_result_dto",
    "validate_round_dto",
    "validate_scoring_group_dto",
    "validate_section_dto",
    "validate_section_update_dto",
    "validate_session_dto",
    "validate_table_dto",
    "validate_td_call_dto",
]

_SECTION_LETTERS_PATTERN = r"^([A-Z])\1{0,2}$"
_STRICT_GUID_CHARS = frozenset("ABCDEF0123456789")
_GUID_MESSAGE = (
    "The guid must be exactly 32 character long and can only contain capital A to F "
    "or digits 0 to 9."
)
_EVENT_GUID_MESSAGE = (
    "The event guid, if used, must be exactly 32 character long and can only contain "
    "capital A to F or digits 0 to 9."
)
_SECTION_LETTERS_HINT = "Valid values are: 'A-Z', 'AA-ZZ' or 'AAA','ZZZ'"

# The valid scoring methods, mirroring the array literals in the C# validators.
_VALID_SCORING_METHODS = (
    ScoringGroupDTO.ScoringType_Pairs,
    ScoringGroupDTO.ScoringType_Imp2_Weighted,
    ScoringGroupDTO.ScoringType_Imp2_10Percent,
    ScoringGroupDTO.ScoringType_Imp2_NoCorrection,
    ScoringGroupDTO.ScoringType_Imp3_Weighted,
    ScoringGroupDTO.ScoringType_Imp3_10Percent,
    ScoringGroupDTO.ScoringType_Imp3_NoCorrection,
    ScoringGroupDTO.ScoringType_XImp2_Total,
    ScoringGroupDTO.ScoringType_XImp2_Average,
    ScoringGroupDTO.ScoringType_XImp3_Total,
    ScoringGroupDTO.ScoringType_XImp3_Average,
    ScoringGroupDTO.ScoringType_TeamImps,
    ScoringGroupDTO.ScoringType_TeamVPDiscrete,
    ScoringGroupDTO.ScoringType_TeamVPContinuous,
    ScoringGroupDTO.ScoringType_Bam,
    ScoringGroupDTO.ScoringType_Patton,
)


def _s(value: str | None) -> str:
    """C# string interpolation renders null as the empty string."""
    return "" if value is None else value


def _enum_name(member: IntEnum) -> str:
    """The C# enum member name: the generated Python enums suffix reserved words with an
    underscore (``None_``), which the C# ``$"{value}"`` interpolation does not have.
    """
    return member.name.removesuffix("_")


def _is_null_or_whitespace(value: str | None) -> bool:
    """C# string.IsNullOrWhiteSpace."""
    return value is None or value.strip() == ""


def _is_invalid_strict_guid(value: str | None) -> bool:
    """The strict guid rule: exactly 32 characters, capitals A-F or digits only."""
    return value is None or len(value) != 32 or any(c not in _STRICT_GUID_CHARS for c in value)


def _is_invalid_section_letters(value: str | None) -> bool:
    """The section-letters rule: 'A'-'Z', 'AA'-'ZZ' or 'AAA'-'ZZZ' (same letter repeated)."""
    return re.match(_SECTION_LETTERS_PATTERN, value or "") is None


def _is_invalid_pin_code(value: str | None) -> bool:
    """The Bridgemate PIN-code rule with C# int.TryParse semantics: the raw value must be four
    characters and parse as an integer (optional sign, surrounding whitespace tolerated,
    no underscores).
    """
    return (
        _is_null_or_whitespace(value)
        or len(value) != 4
        or re.match(r"^[+-]?[0-9]+$", value.strip()) is None
    )


def _participation_to_string(dto: ParticipationDTO) -> str:
    """Port of ParticipationDTO.ToString(), embedded in InitDTO/SectionUpdateDTO messages."""
    swap = "SWAP " if dto.is_player_swap else ""
    return (
        f"{swap}{_s(dto.section_letters)}{dto.table_number} {_enum_name(dto.direction)} "
        f"round {dto.round_number}: {_s(dto.player_number)} {_s(dto.first_name)} {_s(dto.last_name)}"
    )


def validate_participation_dto(
    dto: ParticipationDTO, allow_player_number_and_name: bool = False
) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if dto.session_guid is None or len(dto.session_guid) != 32:
        messages.append(
            f"Invalid SessionGuid ({_s(dto.session_guid)}). The value must be in capitals "
            f"and be exactly 32 characters long."
        )
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if int(dto.direction) < 1 or int(dto.direction) > 4:
        messages.append(
            f"Invalid Direction ({_enum_name(dto.direction)}). The value must be between 1 and 4."
        )
    if dto.table_number < 1:
        messages.append(
            f"Invalid TableNumber ({dto.table_number}). The value must be greater than zero."
        )
    if dto.round_number < 0:
        messages.append(
            f"Invalid RoundNumber ({dto.round_number}). The value cannot be negative."
        )
    if _is_null_or_whitespace(dto.last_name) and _is_null_or_whitespace(dto.player_number):
        messages.append("Either the LastName or the PlayerNumber must be specified.")
    if (
        not allow_player_number_and_name
        and not _is_null_or_whitespace(dto.last_name)
        and not _is_null_or_whitespace(dto.player_number)
    ):
        messages.append("Either the LastName or the PlayerNumber must be specified, but not both.")

    dto.validation_messages = messages
    return not messages


def validate_player_data_dto(dto: PlayerDataDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_null_or_whitespace(dto.player_number):
        messages.append("The PlayerNumber is required.")
    if _is_null_or_whitespace(dto.last_name):
        messages.append("The LastName is required.")

    dto.validation_messages = messages
    return not messages


def validate_round_dto(dto: RoundDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if dto.table_number <= 0:
        messages.append(f"TableNumber ({dto.table_number}) must be greater than zero.")
    if dto.round_number <= 0:
        messages.append(f"RoundNumber ({dto.round_number}) must be greater than zero.")
    if (dto.pair_ns == 0 or dto.pair_ew == 0) and (
        dto.low_board_number > 0 or dto.high_board_number > 0
    ):
        messages.append("No boards may be specified for a sit-out round or an empty round.")

    dto.validation_messages = messages
    return not messages


def validate_table_dto(dto: TableDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if dto.table_number <= 0:
        messages.append(f"TableNumber ({dto.table_number}) must be greater than zero.")

    rounds = dto.rounds or []
    round_numbers = sorted(r.round_number for r in rounds)
    if round_numbers:
        if len(set(round_numbers)) != len(rounds):
            messages.append("The roundnumbers on a table must be unique.")
        if len({value - index for index, value in enumerate(round_numbers)}) != 1:
            messages.append("The roundnumbers must be consecutive.")
        if min(round_numbers) > 1:
            messages.append(
                f"The round numbers must start with 1, but the lowest round is {min(round_numbers)}"
            )

    for round_ in rounds:
        if round_.session_guid != dto.session_guid:
            messages.append(
                f"Round {round_.round_number} on table "
                f"'{_s(dto.section_letters)}{dto.table_number}' "
                f"must have SessionGuid '{_s(dto.session_guid)}' "
                f"but it is '{_s(round_.session_guid)}'"
            )
        if round_.section_letters != dto.section_letters:
            messages.append(
                f"Round {round_.round_number} on table "
                f"' {_s(dto.section_letters)} {dto.table_number}' "
                f"must have SectionLetters '{_s(dto.section_letters)}' "
                f"but it is '{_s(round_.section_letters)}'"
            )
        if round_.table_number != dto.table_number:
            messages.append(
                f"Round {round_.round_number} on table "
                f"' {_s(dto.section_letters)} {dto.table_number}' "
                f"must have TableNumber '{dto.table_number}' "
                f"but it is '{round_.table_number}'"
            )
        if not validate_round_dto(round_):
            error_message = "; ".join(round_.validation_messages or [])
            messages.append(
                f"Round {round_.round_number} on '{_s(dto.section_letters)}{dto.table_number}' "
                f"has validation errrors: {error_message}."
            )

    dto.validation_messages = messages
    return not messages


def _append_table_messages(
    messages: list[str],
    session_guid: str | None,
    letters: str | None,
    tables: list[TableDTO],
) -> None:
    """The table checks shared verbatim between SectionDTO.Validate and
    SectionUpdateDTO.Validate in the C# reference.
    """
    for table in tables:
        if table.session_guid != session_guid:
            messages.append(
                f"Table '{_s(letters)}{table.table_number}' "
                f"must have SessionGuid '{_s(session_guid)}' "
                f"but it is '{_s(table.session_guid)}'"
            )
        if table.section_letters != letters:
            messages.append(
                f"Table ' {_s(letters)} {table.table_number}' "
                f"must have SectionLetters '{_s(letters)}' "
                f"but it is '{_s(table.section_letters)}'"
            )
        if not validate_table_dto(table):
            error_message = "; ".join(table.validation_messages or [])
            messages.append(
                f"Table '{_s(table.section_letters)}{table.table_number}' "
                f"has validation errrors: {error_message}."
            )
    # LINQ GroupBy over the sorted table numbers: duplicates report in ascending key order.
    counts: dict[int, int] = {}
    for number in sorted(table.table_number for table in tables):
        counts[number] = counts.get(number, 0) + 1
    for number, count in counts.items():
        if count > 1:
            messages.append(f"Tablenumber {number} occurs {count} times. ")


def validate_section_dto(dto: SectionDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.letters):
        messages.append(f"Invalid Letters ({_s(dto.letters)}). {_SECTION_LETTERS_HINT}")
    if dto.scoring_group_number <= 0:
        messages.append(
            f"ScoringGroupNumber ({dto.scoring_group_number}) must be greater than zero."
        )
    if dto.missing_pair < 0 and dto.winners != 2:
        messages.append(
            f"MissingPair ({dto.missing_pair}) must at least be zero for a one winner section."
        )
    if dto.winners < 1 or dto.winners > 2:
        messages.append(f"Invalid Winners ({dto.winners}). Valid values are 1 or 2.")
    if dto.game_type not in (10, 20, 30):
        messages.append(f"Invalid GameType ({dto.game_type}). Valid values are 10, 20 or 30.")
    if dto.is_combi_section:
        if _is_invalid_section_letters(dto.north_south_pair_section_letters):
            messages.append(
                f"Invalid NorthSouthPairSectionLetters "
                f"({_s(dto.north_south_pair_section_letters)}). {_SECTION_LETTERS_HINT}"
            )
        if _is_invalid_section_letters(dto.east_west_pair_section_letters):
            messages.append(
                f"Invalid EastWestPairSectionLetters "
                f"({_s(dto.east_west_pair_section_letters)}). {_SECTION_LETTERS_HINT}"
            )
    tables = dto.tables or []
    if abs(dto.ew_move_before_play) > len(tables):
        messages.append(
            f"The absolute value of EWMoveBeforePlay ({dto.ew_move_before_play}) "
            f"cannot be higher than the number of tables ({len(tables)})."
        )

    _append_table_messages(messages, dto.session_guid, dto.letters, tables)

    dto.validation_messages = messages
    return not messages


def validate_section_update_dto(dto: SectionUpdateDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.letters):
        messages.append(f"Invalid Letters ({_s(dto.letters)}). {_SECTION_LETTERS_HINT}")
    if dto.is_deleted:
        if dto.tables:
            messages.append("A deleted section cannot contain tables.")
        dto.validation_messages = messages
        return not messages
    if dto.scoring_group_number <= 0:
        messages.append(
            f"ScoringGroupNumber ({dto.scoring_group_number}) must be greater than zero."
        )
    if dto.scoring_group_scoring_method not in _VALID_SCORING_METHODS:
        messages.append(
            f"Invalid ScoringGroupScoringMethod ({dto.scoring_group_scoring_method}). "
            f"The value must be a multiple of 10 between 10 and 70 or 51. "
        )
    if dto.missing_pair < 0 and dto.winners != 2:
        messages.append(
            f"MissingPair ({dto.missing_pair}) must at least be zero for a one winner section."
        )
    if dto.winners < 1 or dto.winners > 2:
        messages.append(f"Invalid Winners ({dto.winners}). Valid values are 1 or 2.")
    if dto.game_type not in (10, 20, 30):
        messages.append(f"Invalid GameType ({dto.game_type}). Valid values are 10, 20 or 30.")
    if dto.is_combi_section:
        if _is_invalid_section_letters(dto.north_south_pair_section_letters):
            messages.append(
                f"Invalid NorthSouthPairSectionLetters "
                f"({_s(dto.north_south_pair_section_letters)}). {_SECTION_LETTERS_HINT}"
            )
        if _is_invalid_section_letters(dto.east_west_pair_section_letters):
            messages.append(
                f"Invalid EastWestPairSectionLetters "
                f"({_s(dto.east_west_pair_section_letters)}). {_SECTION_LETTERS_HINT}"
            )
    tables = dto.tables or []
    if abs(dto.ew_move_before_play) > len(tables):
        messages.append(
            f"The absolute value of EWMoveBeforePlay ({dto.ew_move_before_play}) "
            f"cannot be higher than the number of tables ({len(tables)})."
        )

    _append_table_messages(messages, dto.session_guid, dto.letters, tables)

    participations = dto.participations or []
    if dto.has_explicit_participations and not participations:
        messages.append(
            f"HasExplicitParticipations is set for section '{_s(dto.letters)}', but the update "
            f"does not carry any Participations. "
            f"An update for such a section must include the complete seating for all rounds."
        )
    for participation in participations:
        description = _participation_to_string(participation)
        if not validate_participation_dto(participation, allow_player_number_and_name=False):
            error_message = "; ".join(participation.validation_messages or [])
            messages.append(
                f"Participation '{description}' has validation errors: {error_message}."
            )
        if participation.session_guid != dto.session_guid:
            messages.append(
                f"Participation '{description}' must have SessionGuid '{_s(dto.session_guid)}' "
                f"but it is '{_s(participation.session_guid)}'."
            )
        if participation.section_letters != dto.letters:
            messages.append(
                f"Participation '{description}' must have SectionLetters '{_s(dto.letters)}' "
                f"but it is '{_s(participation.section_letters)}'."
            )
        if participation.round_number > 1 and not dto.has_explicit_participations:
            messages.append(
                f"Participation '{description}' has RoundNumber {participation.round_number}, "
                f"but section '{_s(dto.letters)}' does not have HasExplicitParticipations set. "
                f"Round numbers greater than one are only valid for sections with "
                f"explicit participations."
            )

    dto.validation_messages = messages
    return not messages


def validate_scoring_group_dto(dto: ScoringGroupDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if dto.scoring_group_number <= 0:
        messages.append(
            f"ScoringGroupNumber ({dto.scoring_group_number}) must be greater than zero."
        )
    if dto.scoring_method not in _VALID_SCORING_METHODS:
        messages.append(
            f"Invalid ScoringMethod ({dto.scoring_method}). "
            f"The value must be a multiple of 10 between 10 and 70 or 51. "
        )
    if dto.is_deleted:
        if dto.sections:
            messages.append(
                "A scoringgroup marked for deletion must not have any sections defined."
            )
    elif not dto.sections:
        messages.append("The scoringgroup must have at least one section.")
    else:
        if len({section.letters for section in dto.sections}) != len(dto.sections):
            messages.append("The sections cannot have the same Letters")

        for section in dto.sections:
            if section.session_guid != dto.session_guid:
                messages.append(
                    f"Section '{_s(section.letters)}' "
                    f"must have SessionGuid '{_s(dto.session_guid)}' "
                    f"but it is '{_s(section.session_guid)}'"
                )
            if section.scoring_group_number != dto.scoring_group_number:
                messages.append(
                    f"Section '{_s(section.letters)}' "
                    f"must have ScoringGroupNumber '{dto.scoring_group_number}' "
                    f"but it is '{section.scoring_group_number}'"
                )

            if not validate_section_dto(section):
                error_message = "; ".join(section.validation_messages or [])
                messages.append(
                    f"Section '{_s(section.letters)}' has validation errrors: {error_message}."
                )

    dto.validation_messages = messages
    return not messages


def validate_session_dto(dto: SessionDTO, for_adding: bool = False) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []

    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)

    if for_adding:
        if not dto.event_guid:
            messages.append("When adding a session the EventGuid must not be empty.")

    if dto.event_guid is not None and (
        len(dto.event_guid) != 32
        or any(c not in _STRICT_GUID_CHARS for c in dto.event_guid)
    ):
        messages.append(_EVENT_GUID_MESSAGE)
    if not dto.scoring_groups:
        messages.append("At least one scoringroup is required.")
        dto.validation_messages = messages
        return False

    if len({group.scoring_group_number for group in dto.scoring_groups}) != len(
        dto.scoring_groups
    ):
        messages.append("The scoring groups cannot have the same ScoringGroupNumber")

    for group in dto.scoring_groups:
        if group.session_guid != dto.session_guid:
            messages.append(
                f"Scoring group with id {group.scoring_group_number} "
                f"must have SessionGuid '{_s(dto.session_guid)}' "
                f"but it is '{_s(group.session_guid)}'"
            )
        if not validate_scoring_group_dto(group):
            error_message = "; ".join(group.validation_messages or [])
            messages.append(
                f"Scoringgroup {group.scoring_group_number} "
                f"has validation errrors: {error_message}."
            )
    sections = [
        section for group in dto.scoring_groups for section in (group.sections or [])
    ]
    if any(section.is_combi_section for section in sections):
        combi_section_groups = [
            (
                section.letters,
                [
                    section.north_south_pair_section_letters,
                    section.east_west_pair_section_letters,
                ],
            )
            for section in sections
            if section.is_combi_section
        ]
        for combi_letters, sources in combi_section_groups:
            if len(set(sources)) != 2:
                messages.append(
                    f"The combisection '{_s(combi_letters)}' must have two different sections "
                    f"as its source, "
                    f"but they are for NS '{_s(sources[0])}' and for EW '{_s(sources[1])}'"
                )
            for source_section in sources:
                if not any(section.letters == source_section for section in sections):
                    messages.append(
                        f"Combisection '{_s(combi_letters)}' specifies section "
                        f"'{_s(source_section)}' as one of its source sections, "
                        f"but this section does not exist."
                    )

    if dto.name is None or len(dto.name) < 1:
        messages.append("The name of the session is required.")

    if dto.year < 2000:
        messages.append(f"The year ({dto.year}) for the session must be at least 2000.")

    if dto.month < 1 or dto.month > 12:
        messages.append(f"The month ({dto.month}) for the session must be between 1 and 12.")

    if dto.day < 1 or dto.day > 31:
        messages.append(f"The day ({dto.day}) for the session must be between 1 and 31.")
    if dto.hour < 0 or dto.hour >= 24:
        messages.append(f"The hour ({dto.hour}) of the day must be between 0 and 23")
    if dto.minute < 0 or dto.minute >= 60:
        messages.append(f"The minute ({dto.minute})must be between 0 and 59")
    try:
        date(dto.year, dto.month, dto.day)
    except Exception:
        messages.append(f"The date {dto.year}-{dto.month}-{dto.day} is invalid.")
    dto.validation_messages = messages
    return not messages


def validate_init_dto(dto: InitDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []

    if dto.commands < 0 or dto.commands > 255:
        messages.append(f"The Commands ({dto.commands}) must be between 0 and 255.")
    if not _is_null_or_whitespace(dto.alternative_data_folder):
        if not os.path.isdir(dto.alternative_data_folder or ""):
            messages.append(
                f"The specified alternative data folder "
                f"('{_s(dto.alternative_data_folder)}' does not exist.)"
            )
    if not dto.sessions:
        messages.append("At least one session is required.")
        dto.validation_messages = messages
        return False

    if len(dto.sessions) > 1:
        if _is_null_or_whitespace(dto.event_guid):
            messages.append(
                f"If there is more than one session the EventGuid must be specified "
                f"and it must be identical to the sessions' EventGuid."
            )
        else:
            for session in dto.sessions:
                if session.event_guid != dto.event_guid:
                    messages.append(
                        f"The EventGuid ('{_s(session.event_guid)}') of session "
                        f"'{_s(session.name)}' ({_s(session.session_guid)}) are not the same."
                    )

    if dto.event_guid is not None and (
        len(dto.event_guid) != 32
        or any(c not in _STRICT_GUID_CHARS for c in dto.event_guid)
    ):
        messages.append(_EVENT_GUID_MESSAGE)

    for session in dto.sessions:
        if not validate_session_dto(session, for_adding=False):
            messages.append(
                f"Session {_s(session.session_guid)} did not validate: "
                f"{', '.join(session.validation_messages or [])}"
            )

    all_section_letters = [
        section.letters
        for session in dto.sessions
        for group in (session.scoring_groups or [])
        for section in (group.sections or [])
    ]
    letters_counts: dict[str | None, int] = {}
    for letters in all_section_letters:
        letters_counts[letters] = letters_counts.get(letters, 0) + 1
    for letters, count in letters_counts.items():
        if count > 1:
            messages.append(
                f"Section '{_s(letters)}' appears {count} times. "
                f"Each section letter must be unique."
            )

    all_scoring_group_numbers = [
        group.scoring_group_number
        for session in dto.sessions
        for group in (session.scoring_groups or [])
    ]
    number_counts: dict[int, int] = {}
    for number in all_scoring_group_numbers:
        number_counts[number] = number_counts.get(number, 0) + 1
    for number, count in number_counts.items():
        if count > 1:
            messages.append(
                f"Scoringgroup '{number}' appears {count} times. "
                f"Each scoringgroup number must be unique."
            )

    if dto.player_data:
        session_guids = [session.session_guid for session in dto.sessions]
        for data in dto.player_data:
            if not validate_player_data_dto(data):
                error_message = ", ".join(data.validation_messages or [])
                messages.append(
                    f"PlayerData '{_s(data.first_name)} {_s(data.last_name)} "
                    f"({_s(data.session_guid)}-{_s(data.player_number)})': {error_message} "
                )
            if data.session_guid not in session_guids:
                messages.append(
                    f"PlayerData.SessionGuid ('{_s(data.session_guid)}') "
                    f"must be one of the sessions' guids "
                    f"({', '.join(_s(guid) for guid in session_guids)})."
                )
        player_number_groups: dict[str, tuple[int, PlayerDataDTO]] = {}
        for data in dto.player_data:
            key = data.player_number or ""
            count, first = player_number_groups.get(key, (0, data))
            player_number_groups[key] = (count + 1, first)
        for count, first in player_number_groups.values():
            if count > 1:
                messages.append(
                    f"Duplicate ({count}) entries for player data "
                    f"'{_s(first.first_name)}+{_s(first.last_name)}'"
                )
    if dto.participations:
        if dto.player_data is None:
            messages.append(
                f"No PlayerDataDTO defined, but there are "
                f"{len(dto.participations)} ParticipationDTOs defined. "
                f"Each ParticipationDTO with its SessionGuid and PlayerNumber properties set "
                f"must have a corresponding PlayerDataDTO that specifies at least its name."
            )
        for participation in dto.participations:
            if not validate_participation_dto(
                participation, allow_player_number_and_name=False
            ):
                error_message = ", ".join(participation.validation_messages or [])
                messages.append(
                    f"ParticipationDTO  '{_s(participation.session_guid)}-"
                    f"{_s(participation.player_number)}': {error_message} "
                )
        for participation in dto.participations:
            combined_id = _s(participation.session_guid) + _s(participation.player_number)
            if combined_id == "" or combined_id == _s(participation.session_guid):
                continue
            if dto.player_data is not None and any(
                _s(data.session_guid) + _s(data.player_number) == combined_id
                for data in dto.player_data
            ):
                continue
            messages.append(
                f"ParticipationDTO '{_s(participation.session_guid)}-"
                f"{_s(participation.player_number)}' "
                f"has no corresponding PlayerDataDTO"
            )
        explicit_section_keys = {
            f"{_s(section.session_guid)}-{_s(section.letters)}"
            for session in dto.sessions
            for group in (session.scoring_groups or [])
            for section in (group.sections or [])
            if section.has_explicit_participations
        }
        for participation in dto.participations:
            if participation.round_number <= 1:
                continue
            key = f"{_s(participation.session_guid)}-{_s(participation.section_letters)}"
            if key not in explicit_section_keys:
                messages.append(
                    f"ParticipationDTO '{_participation_to_string(participation)}' "
                    f"has RoundNumber {participation.round_number}, "
                    f"but section '{_s(participation.section_letters)}' does not have "
                    f"HasExplicitParticipations set. "
                    f"Round numbers greater than one are only valid for sections with "
                    f"explicit participations."
                )
    if dto.handrecords:
        for handrecord in dto.handrecords:
            if not validate_handrecord_dto(handrecord):
                error_message = ", ".join(handrecord.validation_messages or [])
                messages.append(
                    f"HandrecordDTO  '{_s(handrecord.section_letters)}-"
                    f"{handrecord.board_number}': {error_message} "
                )
    if dto.bridgemate2_settings:
        settings_errors = False
        for settings in dto.bridgemate2_settings:
            if not validate_bridgemate2_settings_dto(settings):
                settings_errors = True
                error_message = ", ".join(settings.validation_messages or [])
                messages.append(
                    f"Bridgemate2SettingsDTO  '{_s(settings.section_letters)}': "
                    f"{error_message} "
                )
        if not settings_errors:
            section_letters_groups: dict[str | None, int] = {}
            for settings in dto.bridgemate2_settings:
                section_letters_groups[settings.section_letters] = (
                    section_letters_groups.get(settings.section_letters, 0) + 1
                )
            for letters, count in section_letters_groups.items():
                if count > 1:
                    messages.append(
                        f"Duplicate ({count}) settings for section '{_s(letters)}'"
                    )
    if dto.bridgemate3_settings:
        for settings in dto.bridgemate3_settings:
            if not validate_bridgemate3_settings_dto(settings):
                error_message = ", ".join(settings.validation_messages or [])
                messages.append(
                    f"Bridgemate3SettingsDTO  '{_s(settings.section_letters)}': "
                    f"{error_message} "
                )

    dto.validation_messages = messages
    return not messages


def validate_handrecord_dto(dto: HandrecordDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(
            f"The guid ({_s(dto.session_guid)}) must be exactly 32 character long "
            f"and can only contain capital A to F or digits 0 to 9."
        )
    if dto.scoring_group_number <= 0:
        messages.append(
            f"ScoringGroupNumber ({dto.scoring_group_number}) must be greater than zero."
        )
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if dto.board_number <= 0:
        messages.append(f"BoardNumber ({dto.board_number}) must be greater than zero.")

    all_clubs = [
        ("NorthClubs", dto.north_clubs),
        ("EastClubs", dto.east_clubs),
        ("SouthClubs", dto.south_clubs),
        ("WestClubs", dto.west_clubs),
    ]
    all_diamonds = [
        ("NorthDiamonds", dto.north_diamonds),
        ("EastDiamonds", dto.east_diamonds),
        ("SouthDiamonds", dto.south_diamonds),
        ("WestDiamonds", dto.west_diamonds),
    ]
    all_hearts = [
        ("NorthHearts", dto.north_hearts),
        ("EastHearts", dto.east_hearts),
        ("SouthHearts", dto.south_hearts),
        ("WestHearts", dto.west_hearts),
    ]
    all_spades = [
        ("NorthSpades", dto.north_spades),
        ("EastSpades", dto.east_spades),
        ("SouthSpades", dto.south_spades),
        ("WestSpades", dto.west_spades),
    ]

    all_north = [
        ("NorthClubs", dto.north_clubs),
        ("NorthDiamonds", dto.north_diamonds),
        ("NorthHearts", dto.north_hearts),
        ("NorthSpades", dto.north_spades),
    ]
    all_east = [
        ("EastClubs", dto.east_clubs),
        ("EastDiamonds", dto.east_diamonds),
        ("EastHearts", dto.east_hearts),
        ("EastSpades", dto.east_spades),
    ]
    all_south = [
        ("SouthClubs", dto.south_clubs),
        ("SouthDiamonds", dto.south_diamonds),
        ("SouthHearts", dto.south_hearts),
        ("SouthSpades", dto.south_spades),
    ]
    all_west = [
        ("WestClubs", dto.west_clubs),
        ("WestDiamonds", dto.west_diamonds),
        ("WestHearts", dto.west_hearts),
        ("WestSpades", dto.west_spades),
    ]

    all_suits = all_north + all_east + all_south + all_west

    correct_cards = "".join(sorted("AKQJT98765432"))

    invalid_suits = [
        name
        for name, suit in all_suits
        if suit is None or (not all(card in correct_cards for card in suit) and suit != "")
    ]

    if invalid_suits:
        error_message = ", ".join(invalid_suits)
        messages.append(
            f"Invalid suits (null value or invalid card) in {error_message}. "
            f"Valid cards are '{correct_cards}'"
        )
    else:
        # The invalid-suit check guarantees no None values below.
        def _suit_checks(
            holdings: list[tuple[str, str | None]], count_name: str, duplicate_name: str
        ) -> None:
            combined = "".join(suit or "" for _, suit in holdings)
            if len(combined) != 13:
                messages.append(
                    f"Invalid number of {count_name} ({len(combined)}). "
                    f"The suit must add up to 13 cards."
                )
            else:
                suit_string = "".join(sorted(combined))
                if suit_string != correct_cards:
                    messages.append(
                        f"Duplicate cards in the {duplicate_name} suit '{suit_string}'"
                    )

        _suit_checks(all_clubs, "clubs", "clubs")
        _suit_checks(all_diamonds, "Diamonds", "Diamonds")
        _suit_checks(all_hearts, "Hearts", "Hearts")
        _suit_checks(all_spades, "Spades", "Spades")

        for hand_name, holdings in (
            ("North", all_north),
            ("East", all_east),
            ("South", all_south),
            ("West", all_west),
        ):
            number_of_cards = sum(len(suit or "") for _, suit in holdings)
            if number_of_cards != 13:
                messages.append(
                    f"Invalid number of cards for {hand_name} ({number_of_cards}). "
                    f"The hand must add up to 13 cards."
                )
    dto.validation_messages = messages
    return not messages


def validate_result_dto(dto: ResultDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    if not dto.session_guid or len(dto.session_guid) != 32:
        messages.append(
            f"Invalid SessionGuid ({_s(dto.session_guid)}). "
            f"The value must be in capitals and be exactly"
        )
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if dto.table_number < 1:
        messages.append(
            f"Invalid TableNumber ({dto.table_number}). The value must be greater than zero."
        )
    if dto.round_number < 1:
        messages.append(
            f"Invalid RoundNumber ({dto.round_number}). The value must be greater than zero."
        )
    if dto.board_number < 1:
        messages.append(
            f"Invalid BoardNumber ({dto.board_number}). The value must be greater than zero."
        )
    if dto.is_deleted:
        dto.validation_messages = messages
        return not messages
    if dto.pair_east_west < 1:
        messages.append(
            f"Invalid PairEastWest ({dto.pair_east_west}). "
            f"The value must be greater than zero."
        )
    if dto.pair_north_south < 1:
        messages.append(
            f"Invalid PairNorthSouth ({dto.pair_north_south}). "
            f"The value must be greater than zero."
        )
    if dto.declaring_pair != dto.pair_north_south and dto.declaring_pair != dto.pair_east_west:
        messages.append(
            f"Invalid DeclaringPair ({dto.declaring_pair}). "
            f"The value must be either {dto.pair_north_south} or {dto.pair_east_west}."
        )
    if dto.level >= 1 and (dto.declarer_direction < 1 or dto.declarer_direction > 4):
        messages.append(
            f"Invalid DeclarerDirection ({dto.declarer_direction}). "
            f"The value must be between 1 and 4."
        )
    if dto.level >= 1 and (dto.scoring_direction < 1 or dto.scoring_direction > 3):
        messages.append(
            f"Invalid ScoringDirection ({dto.scoring_direction}). "
            f"The value must be between 1 and 3."
        )
    if dto.level < -10 or dto.level > 7:
        messages.append(
            f"Invalid Level ({dto.level}). The value must be between -10 and +7."
        )
    if (dto.denomination < 1 or dto.denomination > 5) and dto.level >= 1:
        messages.append(
            f"Invalid Denomination ({dto.denomination}). The value must be between 1 and 5."
        )
    if dto.stake < 0 or dto.stake > 2:
        messages.append(f"Invalid Stake ({dto.stake}). The value must be between 0 and 2.")
    if dto.total_tricks < 0 or dto.total_tricks > 13:
        messages.append(
            f"Invalid TotalTricks ({dto.total_tricks}). The value must be between 0 and 13."
        )
    if (dto.lead_card_rank < 2 or dto.lead_card_rank > 14) and dto.lead_card_rank != 0:
        messages.append(
            f"Invalid LeadCardRank ({dto.lead_card_rank}). "
            f"The value must be between 2 and 14 (Ace)."
        )
    elif (dto.lead_card_suit < 1 or dto.lead_card_suit > 4) and dto.lead_card_rank != 0:
        messages.append(
            f"Invalid LeadCardSuit ({dto.lead_card_suit}). "
            f"If LeadCardRank>0  the value must be between 1 and 4."
        )

    dto.validation_messages = messages
    return not messages


def validate_td_call_dto(dto: TdCallDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []

    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    if dto.table_number <= 0:
        messages.append(f"TableNumber ({dto.table_number}) must be greater than zero.")
    if dto.round_number <= 0:
        messages.append(f"RoundNumber ({dto.round_number}) must be greater than zero.")

    if dto.status <= 0 or dto.status > 4:
        messages.append(f"Invalide Status:({dto.status}). Valid values are 1,2,3 or 4.")

    dto.validation_messages = messages
    return not messages


def validate_continue_dto(dto: ContinueDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages: list[str] = []
    mask = (
        255
        & ~InitDTO.StartBCS
        & ~InitDTO.Command_StartReading
        & ~InitDTO.Command_ClearData
        & ~InitDTO.Command_Minimize
        & ~InitDTO.Command_AutoShutDownBPC
        & ~InitDTO.Command_LogLevel_Debug
    )
    if dto.commands & mask != 0:
        messages.append(
            f"Invalid value for Commands ({dto.commands}). "
            f"Valid values are a sum of 0 and/or 1 and/or 4 and/or 128."
        )
    if not _is_null_or_whitespace(dto.alternative_data_folder):
        if not os.path.isdir(dto.alternative_data_folder or ""):
            messages.append(
                f"The specified alternative data folder "
                f"('{_s(dto.alternative_data_folder)}' does not exist.)"
            )
    dto.validation_messages = messages
    return not messages


def _bridgemate_settings_messages(dto: BridgemateSettingsDTO) -> list[str]:
    """Port of the shared BridgemateSettingsDTO.Validate base implementation."""
    messages: list[str] = []
    if _is_invalid_strict_guid(dto.session_guid):
        messages.append(_GUID_MESSAGE)
    if _is_invalid_section_letters(dto.section_letters):
        messages.append(
            f"Invalid SectionLetters ({_s(dto.section_letters)}). {_SECTION_LETTERS_HINT}"
        )
    return messages


def validate_bridgemate2_settings_dto(dto: Bridgemate2SettingsDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages = _bridgemate_settings_messages(dto)
    if _is_invalid_pin_code(dto.bm2_pi_ncode):
        messages.append(
            f"Invalid BM2PINcode ('{_s(dto.bm2_pi_ncode)}'). The pincode must be four digits."
        )

    dto.validation_messages = messages
    return not messages


def validate_bridgemate3_settings_dto(dto: Bridgemate3SettingsDTO) -> bool:
    """Validates the DTO. Produces validation messages if there are problems.

    Returns True if there are no validation errors.
    """
    messages = _bridgemate_settings_messages(dto)
    if dto.bm3_screen_dim_mode < 0 or dto.bm3_screen_dim_mode > 15:
        messages.append(
            f"Invalid BM3ScreenDimMode ({dto.bm3_screen_dim_mode}). "
            f"Value must be between 0 and 15"
        )
    if dto.bm3_screen_brightness < 1 or dto.bm3_screen_brightness > 7:
        messages.append(
            f"Invalid BM3ScreenBrightness ({dto.bm3_screen_brightness}). "
            f"Value must be between 1 and 7"
        )
    if dto.bm3_sleep_mode < 0 or dto.bm3_sleep_mode > 120:
        messages.append(
            f"Invalid BM3SleepMode ({dto.bm3_sleep_mode}). Value must be between 0 and 120"
        )
    if dto.bm3_audio_volume < 0 or dto.bm3_audio_volume > 7:
        messages.append(
            f"Invalid BM3AudioVolume ({dto.bm3_audio_volume}). Value must be between 0 and 7"
        )
    if _is_invalid_pin_code(dto.bm3_pi_ncode):
        messages.append(
            f"Invalid BM3PINcode ('{_s(dto.bm3_pi_ncode)}'). The pincode must be four digits."
        )

    dto.validation_messages = messages
    return not messages
