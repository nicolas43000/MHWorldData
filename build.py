import os.path
import sqlalchemy.orm
import src.db as db

from src.util import ensure, ensure_warn, get_duplicates
from src.data import DataReader

output_filename = 'mhw.db'
supported_ranks = ['lr', 'hr']
supported_languages = ['en']

this_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(this_dir, 'data/')

reader = DataReader(languages=supported_languages, data_path=data_path)

location_map = reader.load_base_map('locations/location_base.json')
item_map = reader.load_base_map("items/item_base.json")
skill_map = reader.load_base_map("skills/skill_base.json")
charm_map = reader.load_base_map('charms/charm_base.json')

monster_map = (reader.start_load("monsters/monster_base.json")
                .add_data("monsters/monster_data.json")
                .add_data("monsters/monster_rewards.json")
                .add_data("monsters/monster_habitats.json", key="habitats")
                .get())

armor_map = (reader.start_load("armors/armor_base.json")
                .add_data("armors/armor_data.json")
                .get())

armorset_map = reader.load_base_map("armors/armorset_base.json")

weapon_map = reader.load_base_map("weapons/weapon_base.json")

decoration_map = (reader.start_load("decorations/decoration_base.json")
                    .add_data("decorations/decoration_chances.json", key="chances")
                    .get())

def validate_monster_rewards():
    # These are validated for 100% drop rate EXACT.
    # Everything else is checked for "at least" 100%
    single_drop_conditions = ("Body Carve", "Tail Carve", "Shiny Drop", "Capture")
    for monster_id, entry in monster_map.items():
        monster_name = entry.name('en') # used for error display

        for condition, sub_condition in entry.get('rewards', {}).items():
            for rank, rewards in sub_condition.items():
                # Ensure correct rank
                ensure(rank in supported_ranks, f"Unsupported rank {rank} in {monster_name} rewards")

                # Ensure percentage is correct (at or greater than 100)
                percentage_sum = sum((r['percentage'] for r in rewards), 0)
                error_start = f"Rewards %'s for monster {monster_name} (rank {rank} condition {condition})"
                if condition in single_drop_conditions:
                    ensure_warn(percentage_sum == 100, f"{error_start} does not sum to 100")
                else:
                    ensure_warn(percentage_sum >= 100, f"{error_start} does not sum to at least 100")

                # check for duplicates (if the condition is relevant)
                if condition in single_drop_conditions:
                    duplicates = get_duplicates((r['item_en'] for r in rewards))
                    ensure_warn(not duplicates, f"Monster {monster_name} contains " +
                        f"duplicate rewards {','.join(duplicates)} in rank {rank} " +
                        f"for condition {condition}")

def build_locations(session : sqlalchemy.orm.Session):
    for location_id, entry in location_map.items():
        for language in supported_languages:
            session.add(db.Location(
                id=location_id,
                lang_id=language,
                name=entry.name(language)
            ))

def build_monsters(session : sqlalchemy.orm.Session):
    for monster_id, entry in monster_map.items():
        monster_name = entry.name('en') # used for error display

        monster = db.Monster(id=entry.id)
        monster.size = entry['size']

        # todo: allow looping over language map entries for a row
        for language in supported_languages:
            monster.translations.append(db.MonsterText(
                lang_id=language,
                name=entry.name(language),
                description=entry['description'][language]
            ))

        for body_part, values in entry['hitzones'].items():
            monster.hitzones.append(db.MonsterHitzone(
                body_part = body_part,
                **values
            ))

        for condition, sub_condition in entry.get('rewards', {}).items():
            for rank, rewards in sub_condition.items():
                for reward in rewards:
                    item_name = reward['item_en']
                    item_id = item_map.id_of('en', item_name)
                    ensure(item_id, f"ERROR: item reward {item_name} in monster {monster_name} does not exist")

                    monster.rewards.append(db.MonsterReward(
                        condition = condition,
                        rank = rank,
                        item_id = item_id,
                        stack_size = reward['stack'],
                        percentage = reward['percentage']
                    ))

        for location_name, habitat_values in entry.get('habitats', {}).items():
            location_id = location_map.id_of("en", location_name)
            ensure(location_id, "Invalid location name " + location_name)

            monster.habitats.append(db.MonsterHabitat(
                location_id=location_id,
                start_area=habitat_values['start_area'] or None,
                move_area=habitat_values['move_area'] or None,
                rest_area=habitat_values['rest_area'] or None
            ))

        session.add(monster)

    print("Built Monsters")

def build_skills(session : sqlalchemy.orm.Session):
    for id, entry in skill_map.items():
        skilltree = db.SkillTree(id=id)

        for language in supported_languages:
            skilltree.translations.append(db.SkillTreeText(
                lang_id=language,
                name=entry.name(language),
                description=entry['description'][language]
            ))

            for effect in entry['effects']:
                skilltree.skills.append(db.Skill(
                    lang_id=language,
                    level=effect['level'],
                    description=effect['description'][language]
                ))

        session.add(skilltree)
    
    print("Built Skills")

def build_items(session : sqlalchemy.orm.Session):
    for id, entry in item_map.items():
        item = db.Item(id=id)
        item.rarity = entry['rarity'] or 0
        item.buy_price = entry['buy_price'] or 0
        item.sell_price = entry['sell_price'] or 0
        item.carry_limit = entry['carry_limit'] or 0

        for language in supported_languages:
            item.translations.append(db.ItemText(
                lang_id=language,
                name=entry.name(language),
                description=entry['description'].get(language, None)
            ))

        session.add(item)
    
    print("Built Items")

def build_armor(session : sqlalchemy.orm.Session):
    # Write entries for armor sets  first
    for set_id, entry in armorset_map.items():
        armor_set = db.ArmorSet(id=set_id) 
        for language in supported_languages:
            armor_set.translations.append(db.ArmorSetText(
                lang_id=language,
                name=entry.name(language)
            ))
        session.add(armor_set)

    for armor_id, entry in armor_map.items():
        armor_name_en = entry.name('en')

        armor = db.Armor(id = armor_id)
        armor.rarity = entry['rarity']
        armor.armor_type = entry['armor_type']
        armor.male = entry['male']
        armor.female = entry['female']
        armor.slot_1 = entry['slots'][0]
        armor.slot_2 = entry['slots'][1]
        armor.slot_3 = entry['slots'][2]
        armor.defense_base = entry['defense_base']
        armor.defense_max = entry['defense_max']
        armor.defense_augment_max = entry['defense_augment_max']
        armor.fire = entry['fire']
        armor.water = entry['water']
        armor.thunder = entry['thunder']
        armor.ice = entry['ice']
        armor.dragon = entry['dragon']

        armorset_id = armorset_map.id_of("en", entry['set'])
        ensure(armorset_id, f"Armorset {entry['set']} in Armor {armor_name_en} does not exist")
        armor.armorset_id = armorset_id

        for language in supported_languages:
            armor.translations.append(db.ArmorText(
                lang_id=language, 
                name=entry.name(language)
            ))

        # Armor Skills
        for skill, level in entry['skills'].items():
            skill_id = skill_map.id_of('en', skill)
            ensure(skill_id, f"Skill {skill} in Armor {armor_name_en} does not exist")
            
            armor.skills.append(db.ArmorSkill(
                skilltree_id=skill_id,
                level=level
            ))
        
        # Armor Crafting
        for item, quantity in entry['craft'].items():
            item_id = item_map.id_of('en', item)
            ensure(item_id, f"Item {item} in Armor {armor_name_en} does not exist")
            
            armor.craft_items.append(db.ArmorRecipe(
                item_id=item_id,
                quantity=quantity
            ))

        session.add(armor)

    print("Built Armor")

def build_weapons(session : sqlalchemy.orm.Session):
    weapon_data = reader.load_split_data_map(weapon_map, "weapons/weapon_data")

    # Prepass to determine which weapons are "final"
    # All items that are a previous to another are "not final"
    all_final = set(weapon_data.keys())
    for entry in weapon_data.values():
        if not entry.get('previous', None):
            continue
        try:
            prev_id = weapon_map.id_of('en', entry['previous'])
            all_final.remove(prev_id)
        except KeyError:
            pass

    for weapon_id, entry in weapon_data.items():
        weapon = db.Weapon(id = weapon_id)
        weapon.weapon_type = entry['weapon_type']
        weapon.rarity = entry['rarity']
        weapon.attack = entry['attack']
        weapon.slot_1 = entry['slots'][0]
        weapon.slot_2 = entry['slots'][1]
        weapon.slot_3 = entry['slots'][2]

        weapon.element_type = entry['element_type']
        weapon.element_damage = entry['element_damage']
        weapon.element_hidden = entry['element_hidden']

        # todo: sharpness, coatings, ammo

        # Note: High probably the way this is stored in data will be refactored
        # Possibilities are either split weapon_data files, or separated sub-data files
        weapon.glaive_boost_type = entry.get('glaive_boost_type', None)
        weapon.deviation = entry.get('deviation', None)
        weapon.special_ammo = entry.get('special_ammo', None)
        
        weapon.craftable = bool(entry.get('craft', False))
        weapon.final = weapon_id in all_final

        if entry.get('previous', None):
            previous_weapon_id = weapon_map.id_of("en", entry['previous'])
            ensure(previous_weapon_id, f"Weapon {entry['previous']} does not exist")
            weapon.previous_weapon_id = previous_weapon_id

        # Add language translations
        for language in supported_languages:
            weapon.translations.append(db.WeaponText(
                lang_id = language,
                name = entry.name(language)
            ))

        # Add crafting/upgrade recipes
        for recipe_type in ('craft', 'upgrade'):
            recipe = entry.get(recipe_type, {}) or {}
            for item, quantity in recipe.items():
                item_id = item_map.id_of("en", item)
                ensure(item_id, f"Item {item_id} in weapon {entry.name('en')} does not exist")
                session.add(db.WeaponRecipe(
                    weapon_id = weapon_id,
                    item_id = item_id,
                    quantity = quantity,
                    recipe_type = recipe_type
                ))
        
        session.add(weapon)

    print("Built Weapons")

def build_decorations(session : sqlalchemy.orm.Session):
    "Performs the build process for decorations. Must be done after skills"

    for decoration_id, entry in decoration_map.items():
        skill_id = skill_map.id_of('en', entry['skill_en'])
        ensure(skill_id, f"Decoration {entry.name('en')} refers to " +
            f"skill {entry['skill_en']}, which doesn't exist.")

        ensure("chances" in entry, "Missing chance data for " + entry.name('en'))
        
        decoration = db.Decoration(
            id=decoration_id,
            rarity=entry['rarity'],
            slot=entry['slot'],
            skilltree_id=skill_id,
            mysterious_feystone_chance=entry['chances']['mysterious_feystone_chance'],
            glowing_feystone_chance=entry['chances']['glowing_feystone_chance'],
            worn_feystone_chance=entry['chances']['worn_feystone_chance'],
            warped_feystone_chance=entry['chances']['warped_feystone_chance']
        )

        for language in supported_languages:
            decoration.translations.append(db.DecorationText(
                lang_id=language,
                name=entry.name('en')
            ))

        session.add(decoration)

    print("Built Decorations")

def build_charms(session : sqlalchemy.orm.Session):
    for charm_id, entry in charm_map.items():
        charm = db.Charm(id=charm_id)

        for language in supported_languages:
            charm.translations.append(db.CharmText(
                lang_id=language,
                name=entry.name(language)
            ))

        for skill_en, level in entry['skills'].items():
            skill_id = skill_map.id_of('en', skill_en)
            ensure(skill_id, f"Charm {entry.name('en')} refers to " +
                f"item {skill_en}, which doesn't exist.")

            charm.skills.append(db.CharmSkill(
                skilltree_id=skill_id,
                level=level
            ))

        for item_en, quantity in entry['craft'].items():
            item_id = item_map.id_of('en', item_en)
            ensure(item_id, f"Charm {entry.name('en')} refers to " +
                f"item {item_en}, which doesn't exist.")

            charm.craft_items.append(db.CharmRecipe(
                item_id=item_id,
                quantity=quantity
            ))

        session.add(charm)

    print("Built Charms")

import sys

def build_database(output_filename):
    # Python 3.6 dictionaries preserve insertion order, and python 3.7 added it to the spec officially
    # Older versions of python won't maintain order when importing data for the build.
    if sys.version_info < (3,6):
        print(f"WARNING: You are running python version {sys.version}, " +
            "but this application was designed for Python 3.6 and newer. ")
        print("Earlier versions of Python will still build the project, but will not have a consistent build.")
        print("When creating a final build, make sure to use a newer version of python.")

    sessionbuilder = db.recreate_database(output_filename)

    validate_monster_rewards()

    with db.session_scope(sessionbuilder) as session:
        build_items(session)
        build_locations(session)
        build_monsters(session)
        build_skills(session)
        build_armor(session)
        build_weapons(session)
        build_decorations(session)
        build_charms(session)
        
    print("Finished build")

if __name__ == '__main__':
    build_database(output_filename)
