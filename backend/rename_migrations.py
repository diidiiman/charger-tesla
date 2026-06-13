import os
import re

MAPPING = {
    "59d241768575": "0001",
    "5d93641379e8": "0002",
    "7d5c1d88514e": "0003",
    "1d500af9ee6e": "0004",
    "a94878e0dcb6": "0005",
    "6aaf6f306752": "0006",
    "facb8bab9c27": "0007",
    "62e62d95f5d7": "0008",
}


def process_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    filename = os.path.basename(filepath)
    # The file looks like <rev>_<slug>.py
    # we want <new_rev>_<slug>.py
    match = re.match(r"^([a-f0-9]+)_(.*?)$", filename)
    if not match:
        return
    old_rev = match.group(1)
    slug = match.group(2)
    if old_rev not in MAPPING:
        return
    new_rev = MAPPING[old_rev]
    new_filename = f"{new_rev}_{slug}"

    # Replace revision identifiers inside the file
    content = re.sub(
        r"revision: str = ['\"]" + old_rev + r"['\"]",
        f"revision: str = '{new_rev}'",
        content,
    )
    content = re.sub(r"Revision ID: " + old_rev, f"Revision ID: {new_rev}", content)

    # Replace down_revisions
    for old_down_rev, new_down_rev in MAPPING.items():
        content = re.sub(
            r"down_revision: Union\[str, None\] = ['\"]" + old_down_rev + r"['\"]",
            f"down_revision: Union[str, None] = '{new_down_rev}'",
            content,
        )
        content = re.sub(
            r"Revises: " + old_down_rev, f"Revises: {new_down_rev}", content
        )

    with open(filepath, "w") as f:
        f.write(content)

    os.rename(filepath, os.path.join(os.path.dirname(filepath), new_filename))


versions_dir = "migrations/versions"
for filename in os.listdir(versions_dir):
    if filename.endswith(".py"):
        process_file(os.path.join(versions_dir, filename))
