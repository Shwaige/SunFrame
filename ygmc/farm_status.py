import html
import re
from dataclasses import dataclass

from ygmc.config import Account, HOME_PATH
from ygmc.http import HttpClient
from ygmc.session import refresh_game_account, resolve_game_account


@dataclass
class FarmStatusResult:
    ok: bool
    credential_source: str
    field_count: int
    ranch_count: int
    farm_friend_count: int
    ranch_friend_count: int


def _clean_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.S)
    return html.unescape(text).replace("\r", "").replace("\n", "").strip()


def parse_pet_status(page: str) -> tuple[str, str]:
    pet_match = re.search(r"宠物:([^<]+?)\.<a ", page)
    explore_match = re.search(r"探险宠物:([^<]+?)\.<a ", page)
    pet = _clean_text(pet_match.group(1)) if pet_match else ""
    explore = _clean_text(explore_match.group(1)) if explore_match else ""
    return pet, explore


def parse_onekey_status(page: str) -> str:
    match = re.search(r"一键:.*?\((.*?)\)\s*<br/>", page, re.S)
    return _clean_text(match.group(1)) if match else ""


def parse_fields(page: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    pattern = re.compile(
        r"fieldDetail\.go[^>]*fieldId=([a-f0-9]+)[^>]*>([^<]+)</a>:(?:<a [^>]*>)?([^<\n]+)(?:</a>)?\s*(.*?)<br/>",
        re.S,
    )
    for match in pattern.finditer(page):
        field_id, field_name, crop_name, rest = match.groups()
        status = _clean_text(rest)
        fields.append(
            {
                "field_id": field_id,
                "field_name": _clean_text(field_name),
                "crop_name": _clean_text(crop_name),
                "status": status,
            }
        )
    return fields


def parse_space_field(page: str) -> dict[str, str] | None:
    match = re.search(r"太空舱</a>:([^<]+)\.<a [^>]*fieldId=([a-f0-9]+)[^>]*>\[播种\]</a>", page)
    if not match:
        return None
    action_text, field_id = match.groups()
    return {"field_id": field_id, "field_name": "太空舱", "crop_name": _clean_text(action_text), "status": "可播种"}


def parse_ranch_onekey_status(page: str) -> str:
    match = re.search(r"一键:.*?\((.*?)\)\s*<br/>", page, re.S)
    return _clean_text(match.group(1)) if match else ""


def parse_ranch_sections(page: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    section_pattern = re.compile(
        r"【<a [^>]*>([^<]+)</a>】容纳动物：([^<]+)<br/>\s*([^<]+)\((\d+/\d+)\)",
        re.S,
    )
    for match in section_pattern.finditer(page):
        area_name, capacity, fodder_name, fodder_amount = match.groups()
        sections.append(
            {
                "area_name": _clean_text(area_name),
                "capacity": _clean_text(capacity),
                "fodder_name": _clean_text(fodder_name),
                "fodder_amount": _clean_text(fodder_amount),
            }
        )
    return sections


def parse_ranch_animals(page: str) -> list[dict[str, str]]:
    animals: list[dict[str, str]] = []
    pattern = re.compile(
        r"\[(窝|栏)(\d+)\]([^:]+):<a [^>]*siteId=([a-f0-9]+)[^>]*>(.*?)</a>\s*(.*?)<br/>",
        re.S,
    )
    for match in pattern.finditer(page):
        area_type, slot_no, quality, site_id, animal_name, rest = match.groups()
        status = _clean_text(rest)
        animals.append(
            {
                "area_type": _clean_text(area_type),
                "slot_no": _clean_text(slot_no),
                "quality": _clean_text(quality),
                "site_id": site_id,
                "animal_name": _clean_text(animal_name),
                "status": status,
            }
        )
    return animals


def parse_friend_list(page: str, kind: str) -> list[dict[str, str]]:
    if kind == "farm":
        path = "friendFields.go"
    else:
        path = "friendSites.go"
    friends: list[dict[str, str]] = []
    pattern = re.compile(
        rf"(\d+)\.\s*<a href='[^']*{path}[^']*otherId=([a-f0-9]+)'>(.*?)</a>\s*(\[[^]]+\])?",
        re.S,
    )
    for match in pattern.finditer(page):
        order_no, other_id, nickname, tag = match.groups()
        friends.append(
            {
                "order_no": _clean_text(order_no),
                "other_id": other_id,
                "nickname": _clean_text(nickname),
                "tag": _clean_text(tag or ""),
            }
        )
    return friends


def _fetch_status_pages(account: Account) -> tuple[HttpClient, dict[str, str], str, str, str, str]:
    params = {"openId": account.open_id, "sid": account.sid}
    client = HttpClient()
    farm_page = client.fetch(HOME_PATH, params)
    ranch_page = client.fetch(HOME_PATH, {**params, "indexType": "1"})
    farm_friends_page = client.fetch("/ygmc/farm/myFriends.go", params)
    ranch_friends_page = client.fetch("/ygmc/ranch/myFriends.go", params)
    return client, params, farm_page, ranch_page, farm_friends_page, ranch_friends_page


def _status_looks_abnormal(
    farm_page: str,
    ranch_page: str,
    farm_friends_page: str,
    ranch_friends_page: str,
) -> bool:
    fields = parse_fields(farm_page)
    if parse_space_field(farm_page):
        fields.append({"field_id": "space", "field_name": "", "crop_name": "", "status": ""})
    ranch_animals = parse_ranch_animals(ranch_page)
    farm_friends = parse_friend_list(farm_friends_page, "farm")
    ranch_friends = parse_friend_list(ranch_friends_page, "ranch")
    return not fields and not ranch_animals and not farm_friends and not ranch_friends


def run_farm_status(account: Account) -> FarmStatusResult:
    game_account, credential_source = resolve_game_account(account)
    client, params, farm_page, ranch_page, farm_friends_page, ranch_friends_page = _fetch_status_pages(game_account)
    if credential_source == "cache" and account.has_login_credentials:
        if _status_looks_abnormal(farm_page, ranch_page, farm_friends_page, ranch_friends_page):
            game_account, credential_source = refresh_game_account(account)
            client, params, farm_page, ranch_page, farm_friends_page, ranch_friends_page = _fetch_status_pages(
                game_account
            )

    print(f"credential_source={credential_source}")
    print(f"resolved_open_id={game_account.open_id}")
    print(f"resolved_sid={game_account.sid}")

    pet, explore_pet = parse_pet_status(farm_page)
    if pet:
        print(f"pet_status={pet}")
    if explore_pet:
        print(f"explore_pet_status={explore_pet}")

    onekey_status = parse_onekey_status(farm_page)
    if onekey_status:
        print(f"farm_onekey_status={onekey_status}")

    fields = parse_fields(farm_page)
    space_field = parse_space_field(farm_page)
    if space_field:
        fields.append(space_field)

    for idx, field in enumerate(fields, start=1):
        print(
            f"field_{idx}="
            f"{field['field_name']}|{field['crop_name']}|{field['status']}|fieldId={field['field_id']}"
        )

    ranch_onekey_status = parse_ranch_onekey_status(ranch_page)
    if ranch_onekey_status:
        print(f"ranch_onekey_status={ranch_onekey_status}")

    ranch_sections = parse_ranch_sections(ranch_page)
    for idx, section in enumerate(ranch_sections, start=1):
        print(
            f"ranch_section_{idx}="
            f"{section['area_name']}|capacity={section['capacity']}|"
            f"{section['fodder_name']}={section['fodder_amount']}"
        )

    ranch_animals = parse_ranch_animals(ranch_page)
    for idx, animal in enumerate(ranch_animals, start=1):
        print(
            f"ranch_{idx}="
            f"{animal['area_type']}{animal['slot_no']}|{animal['quality']}|"
            f"{animal['animal_name']}|{animal['status']}|siteId={animal['site_id']}"
        )

    farm_friends = parse_friend_list(farm_friends_page, "farm")
    for idx, friend in enumerate(farm_friends, start=1):
        print(
            f"farm_friend_{idx}="
            f"{friend['nickname']}|tag={friend['tag'] or '无'}|otherId={friend['other_id']}"
        )

    ranch_friends = parse_friend_list(ranch_friends_page, "ranch")
    for idx, friend in enumerate(ranch_friends, start=1):
        print(
            f"ranch_friend_{idx}="
            f"{friend['nickname']}|tag={friend['tag'] or '无'}|otherId={friend['other_id']}"
        )

    print(f"field_count={len(fields)}")
    print(f"ranch_count={len(ranch_animals)}")
    print(f"farm_friend_count={len(farm_friends)}")
    print(f"ranch_friend_count={len(ranch_friends)}")
    return FarmStatusResult(
        ok=True,
        credential_source=credential_source,
        field_count=len(fields),
        ranch_count=len(ranch_animals),
        farm_friend_count=len(farm_friends),
        ranch_friend_count=len(ranch_friends),
    )
