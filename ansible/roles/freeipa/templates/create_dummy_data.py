#!/usr/bin/env python3

from contextlib import suppress, contextmanager

from faker import Faker

import python_freeipa

USER_PASSWORD = "password"

fake = Faker()
fake.seed_instance(0)


def rando(percentage):
    if fake.random_int(min=0, max=100, step=1) < percentage:
        return True
    else:
        return False

@contextmanager
def handle_already_a_member():
    try:
        yield
    except python_freeipa.exceptions.ValidationError as e:
        if e.args[0]["member"]["user"][0][1] == "This entry is already a member":
            pass
        else:
            raise


groups = {
    "developers": 80,
    "designers": 30,
    "elections": 10,
    "sysadmin-calendar": 10,
    "infra": 20,
    "QA": 20,
    "translators": 10,
    "ambassadors": 30,
}

ipa = python_freeipa.ClientLegacy(
    host="{{ ansible_fqdn }}", verify_ssl="/etc/ipa/ca.crt"
)
ipa.login("{{ ipa_admin_user }}", "{{ ipa_admin_password }}")

untouched_ipa = python_freeipa.ClientLegacy(
    host="{{ ansible_fqdn }}", verify_ssl="/etc/ipa/ca.crt"
)

agreement_name = "FPCA"
group_name = f"signed_{agreement_name}"
with suppress(python_freeipa.exceptions.DuplicateEntry):
    ipa._request("fasagreement_add", agreement_name, {"description": f"This is the {agreement_name} agreement"})
    ipa.group_add(group_name, f"Signers of the {agreement_name}")
    ipa._request("automember_add", group_name, {"type":"group"})
    ipa._request("automember_add_condition", group_name, {"type":"group", "key":"memberof", "automemberinclusiveregex":f"^cn={agreement_name},cn=fasagreements,"})

for group in groups.keys():
    with suppress(python_freeipa.exceptions.DuplicateEntry):
        ipa.group_add(group, f"A group for {group}", fasgroup=True)
        ipa._request("fasagreement_add_group", agreement_name, {"group": group})

with suppress(python_freeipa.exceptions.DuplicateEntry):
    ipa.group_add("general", f"A group for general stuff", fasgroup=True)


for x in range(100):
    firstName = fake.first_name()
    lastName = fake.last_name()
    username = firstName + lastName
    fullname = firstName + " " + lastName
    print(f"adding user {username} - {fullname}")
    with suppress(python_freeipa.exceptions.DuplicateEntry):
        ipa.user_add(
            username,
            firstName,
            lastName,
            fullname,
            disabled=False,
            user_password=USER_PASSWORD,
            fasircnick=[username, username + "_"],
            faslocale="en-US",
            fastimezone="Australia/Brisbane",
            fasstatusnote="active",
            fasgpgkeyid=[],
        )

        untouched_ipa.change_password(
            username, new_password=USER_PASSWORD, old_password=USER_PASSWORD
        )

    with handle_already_a_member():
        has_signed_fpca = False
        if rando(90):
            ipa._request("fasagreement_add_user", "FPCA", {"user": username})
            has_signed_fpca = True
        else:
            ipa.group_add_member("general", username)

    # add to groups
    for groupname, chance in groups.items():
        if rando(chance) and has_signed_fpca:
            with handle_already_a_member():
                ipa.group_add_member(groupname, username)
                # add member manager (sponsor)
                if rando(30):
                    ipa._request(
                        "group_add_member_manager", groupname, {"user": username}
                    )
