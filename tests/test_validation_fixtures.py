"""Golden validation-parity fixtures.

Each fixture holds a DTO payload plus the boolean result and the exact validation messages the
.NET reference client's Validate() method produced for it. The hand-ported validators in
bridgemate_dataconnector.validation must reproduce both, message for message and in order.
"""

import json
from pathlib import Path

import pytest

from bridgemate_dataconnector import validation
from bridgemate_dataconnector.dto import (
    Bridgemate2SettingsDTO,
    Bridgemate3SettingsDTO,
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

FIXTURES = Path(__file__).parent / "fixtures" / "validation"
VALIDATION_FIXTURES = sorted(FIXTURES.glob("*.json"))

# Maps the fixture's Dto name to the DTO class and its validator.
VALIDATORS = {
    "Bridgemate2SettingsDTO": (Bridgemate2SettingsDTO, validation.validate_bridgemate2_settings_dto),
    "Bridgemate3SettingsDTO": (Bridgemate3SettingsDTO, validation.validate_bridgemate3_settings_dto),
    "ContinueDTO": (ContinueDTO, validation.validate_continue_dto),
    "HandrecordDTO": (HandrecordDTO, validation.validate_handrecord_dto),
    "InitDTO": (InitDTO, validation.validate_init_dto),
    "ParticipationDTO": (ParticipationDTO, validation.validate_participation_dto),
    "PlayerDataDTO": (PlayerDataDTO, validation.validate_player_data_dto),
    "ResultDTO": (ResultDTO, validation.validate_result_dto),
    "RoundDTO": (RoundDTO, validation.validate_round_dto),
    "ScoringGroupDTO": (ScoringGroupDTO, validation.validate_scoring_group_dto),
    "SectionDTO": (SectionDTO, validation.validate_section_dto),
    "SectionUpdateDTO": (SectionUpdateDTO, validation.validate_section_update_dto),
    "SessionDTO": (SessionDTO, validation.validate_session_dto),
    "TableDTO": (TableDTO, validation.validate_table_dto),
    "TdCallDTO": (TdCallDTO, validation.validate_td_call_dto),
}


@pytest.mark.parametrize("path", VALIDATION_FIXTURES, ids=lambda p: p.stem)
def test_validation_matches_reference(path: Path):
    fixture = json.loads(path.read_text(encoding="utf-8"))
    dto_class, validator = VALIDATORS[fixture["Dto"]]
    dto = dto_class.from_dict(fixture["Payload"])
    args = fixture.get("Args") or {}

    if fixture["Dto"] == "ParticipationDTO":
        result = validator(dto, allow_player_number_and_name=args.get("allowPlayerNumberAndName", False))
    elif fixture["Dto"] == "SessionDTO":
        result = validator(dto, for_adding=args.get("forAdding", False))
    else:
        result = validator(dto)

    assert result == fixture["ExpectedValid"]
    assert (dto.validation_messages or []) == fixture["ExpectedMessages"]


# The AlternativeDataFolder rule (Directory.Exists in the C# reference) has no golden fixture
# because the result depends on the local file system; these tests pin the port natively.


def test_init_dto_alternative_data_folder_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    dto = InitDTO(commands=1, alternative_data_folder=str(missing))
    assert validation.validate_init_dto(dto) is False
    assert dto.validation_messages == [
        f"The specified alternative data folder ('{missing}' does not exist.)",
        "At least one session is required.",
    ]


def test_init_dto_alternative_data_folder_existing(tmp_path: Path):
    dto = InitDTO(commands=1, alternative_data_folder=str(tmp_path))
    assert validation.validate_init_dto(dto) is False
    assert dto.validation_messages == ["At least one session is required."]


def test_continue_dto_alternative_data_folder_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    dto = ContinueDTO(commands=1, alternative_data_folder=str(missing))
    assert validation.validate_continue_dto(dto) is False
    assert dto.validation_messages == [
        f"The specified alternative data folder ('{missing}' does not exist.)"
    ]


def test_continue_dto_alternative_data_folder_existing(tmp_path: Path):
    dto = ContinueDTO(commands=1, alternative_data_folder=str(tmp_path))
    assert validation.validate_continue_dto(dto) is True
    assert dto.validation_messages == []
