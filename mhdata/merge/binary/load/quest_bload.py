'''
Module file detected to loading quest binary data, but not saving or converting it.
'''

from typing import Iterable
from pathlib import Path

from .bcore import load_schema, load_text, get_chunk_root
from mhdata.merge.binary.parsers import read_struct_from_file, Mib, load_quest, RemFile

class QuestInfo:
    "An encapsulation of quest binary data and referenced cross data"
    def __init__(self, name, binary: Mib, reward_data_list):
        self.name = name
        self.binary = binary
        self.reward_data_list = reward_data_list

def load_quests() -> Iterable[QuestInfo]:
    quests = []
    quest_base_path = Path(get_chunk_root()).joinpath('quest')
    rem_base_path = quest_base_path.joinpath('rem')

    quest_files = quest_base_path.rglob("*.mib")

    for path in quest_files:
        quest_text_fname = path.stem.replace('questData_', 'q')
        quest_text = load_text(f'common/text/quest/{quest_text_fname}')

        name = quest_text[0]

        # todo: disable this line if we wanna find out other ways to mark something as invalid
        if name['en'] in ('Unavailable', 'Invalid Message'):
            continue

        binary = load_quest(path)

        # Load REMS (reward files)
        rem_ids = binary.objective_section.rem_ids
        rem_files = [rem_base_path.joinpath(f'remData_{rem_id}.rem') for rem_id in rem_ids]
        rem_files = filter(lambda r: r.exists(), rem_files)
        rem_files = [read_struct_from_file(path, RemFile) for path in rem_files]

        quests.append(QuestInfo(name, binary, rem_files))

    return quests

