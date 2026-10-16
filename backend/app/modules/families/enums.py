from enum import StrEnum


class MemberRole(StrEnum):
    ADULT = "adult"
    CHILD = "child"


class AgeGroup(StrEnum):
    AGE_6_7 = "6-7"
    AGE_8_10 = "8-10"
    AGE_11_13 = "11-13"
