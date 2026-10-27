//! Unit settings and stats

use crate::types::{SkillType, TribeType, UnitType};

/// A unit's skills as a bit set (SkillType values are 0..=63): `contains` is a mask test, no hashing.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct SkillSet(u64);

impl SkillSet {
    pub fn new() -> Self {
        Self(0)
    }
    pub fn insert(&mut self, skill: SkillType) -> bool {
        let bit = 1u64 << (skill as i8 as u32);
        let new = self.0 & bit == 0;
        self.0 |= bit;
        new
    }
    #[inline]
    pub fn contains(&self, skill: &SkillType) -> bool {
        self.0 & (1u64 << (*skill as i8 as u32)) != 0
    }
}

/// Unit stat configuration
#[derive(Debug, Clone)]
pub struct UnitSetting {
    pub cost: i32,
    pub attack: f32,
    pub movement: i32,
    pub defense: f32,
    pub range: i32,
    pub health: f32, // todo move to Option to enfoce passenger inheritance?
    pub upgrade_from: Option<UnitType>,
    pub is_unique: bool,
    pub skills: SkillSet,
    pub is_super: bool,
    pub tribe_type: TribeType,
}

impl Default for UnitSetting {
    fn default() -> Self {
        Self {
            cost: 0,
            attack: 0.0,
            movement: 1,
            defense: 0.0,
            range: 1,
            health: 10.0,
            upgrade_from: None,
            is_unique: false,
            skills: SkillSet::new(),
            is_super: false,
            tribe_type: TribeType::None,
        }
    }
}

/// Helper macro to create skill sets
macro_rules! skills {
    ($($skill:expr),* $(,)?) => {{
        let mut set = SkillSet::new();
        $(set.insert($skill);)*
        set
    }};
}

/// Get unit settings by type (built once, shared)
pub fn get_unit_setting(unit_type: UnitType) -> &'static UnitSetting {
    static TABLE: std::sync::OnceLock<Vec<Option<UnitSetting>>> = std::sync::OnceLock::new();
    let table = TABLE.get_or_init(|| {
        (-128i16..128)
            .map(|i| UnitType::from_repr(i as i8).map(build_unit_setting))
            .collect()
    });
    table[(unit_type as i8 as i16 + 128) as usize]
        .as_ref()
        .expect("unit type in table")
}

fn build_unit_setting(unit_type: UnitType) -> UnitSetting {
    use SkillType as S;
    use UnitType as U;

    match unit_type {
        U::None => UnitSetting {
            cost: -1,
            attack: -1.0,
            health: 1.0,
            ..Default::default()
        },

        U::Warrior => UnitSetting {
            cost: 2,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Fortify],
            ..Default::default()
        },
        U::Rider => UnitSetting {
            cost: 3,
            attack: 2.0,
            movement: 2,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Escape, S::Fortify],
            ..Default::default()
        },
        U::Knight => UnitSetting {
            cost: 8,
            attack: 3.5,
            movement: 3,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Persist, S::Fortify],
            ..Default::default()
        },
        U::Defender => UnitSetting {
            cost: 3,
            attack: 1.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Fortify],
            ..Default::default()
        },
        U::Catapult => UnitSetting {
            cost: 8,
            attack: 4.0,
            movement: 1,
            defense: 0.0,
            range: 3,
            health: 10.0,
            skills: skills![S::Stiff],
            ..Default::default()
        },
        U::Archer => UnitSetting {
            cost: 3,
            attack: 2.0,
            movement: 1,
            defense: 1.0,
            range: 2,
            health: 10.0,
            skills: skills![S::Dash, S::Fortify],
            ..Default::default()
        },
        U::MindBender => UnitSetting {
            cost: 5,
            attack: 0.0,
            movement: 1,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::HealOthers, S::Convert, S::Stiff],
            ..Default::default()
        },
        U::Swordsman => UnitSetting {
            cost: 5,
            attack: 3.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Dash],
            ..Default::default()
        },
        U::Giant => UnitSetting {
            cost: 10,
            attack: 5.0,
            movement: 1,
            defense: 4.0,
            range: 1,
            health: 40.0,
            is_super: true,
            skills: skills![S::Static],
            ..Default::default()
        },

        // Agent units
        U::Cloak => UnitSetting {
            cost: 8,
            attack: 2.0, // v123 card (UNIT-STATS-UI)
            movement: 2,
            defense: 0.5,
            range: 1,
            health: 5.0,
            skills: skills![
                S::Hide,
                S::Stiff, // v123 card
                S::Infiltrate,
                S::Dash,
                S::Scout,
                S::Creep,
                S::Static
            ],
            ..Default::default()
        },
        U::Dagger => UnitSetting {
            cost: 2,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Surprise, S::Independent, S::Static],
            ..Default::default()
        },
        U::Pirate => UnitSetting {
            cost: 2,
            attack: 2.0,
            movement: 2,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![
                S::Carry,
                S::Float,
                S::Dash,
                S::Surprise,
                S::Independent,
                S::Static
            ],
            ..Default::default()
        },
        U::Dinghy => UnitSetting {
            cost: 2,
            attack: 0.0,
            movement: 2,
            defense: 0.5,
            range: 1,
            health: 5.0,
            skills: skills![
                S::Carry,
                S::Float,
                S::Hide,
                S::Infiltrate,
                S::Dash,
                S::Scout,
                S::Static
            ],
            ..Default::default()
        },

        // Navy
        U::Raft => UnitSetting {
            cost: 0,
            attack: 0.0,
            movement: 2,
            defense: 1.0,
            range: 2,
            health: 10.0,
            skills: skills![S::Carry, S::Float, S::Static, S::Stiff],
            ..Default::default()
        },
        U::Scoutship => UnitSetting {
            cost: 5,
            attack: 2.0,
            movement: 3,
            defense: 1.0,
            range: 2,
            health: 10.0, // inherits
            upgrade_from: Some(U::Raft),
            skills: skills![S::Carry, S::Dash, S::Float, S::Static, S::Scout],
            ..Default::default()
        },
        U::Rammership => UnitSetting {
            cost: 5,
            attack: 3.0,
            movement: 3,
            defense: 3.0,
            range: 1,
            health: 10.0,
            upgrade_from: Some(U::Raft),
            skills: skills![S::Dash, S::Float, S::Carry, S::Static],
            ..Default::default()
        },
        U::Bomber => UnitSetting {
            cost: 15,
            attack: 3.0,
            movement: 2,
            defense: 2.0,
            range: 3,
            health: 10.0,
            upgrade_from: Some(U::Raft),
            skills: skills![S::Carry, S::Float, S::Splash, S::Stiff, S::Static],
            ..Default::default()
        },
        U::Juggernaut => UnitSetting {
            cost: 10,
            attack: 4.0,
            movement: 2,
            defense: 4.0,
            range: 1,
            health: 40.0,
            is_super: true,
            skills: skills![S::Float, S::Carry, S::Stiff, S::Stomp, S::Static],
            ..Default::default()
        },

        // Aquarion
        U::Crab => UnitSetting {
            cost: 10,
            attack: 4.0,
            movement: 2,
            defense: 5.0,
            range: 1,
            health: 40.0,
            is_super: true,
            skills: skills![S::Escape, S::Static, S::AutoFlood, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        U::Amphibian => UnitSetting {
            cost: 3,
            attack: 2.0,
            movement: 2,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Escape, S::Fortify, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        // v123 info cards (data/measured_ui.json; UNIT-STATS-UI, AQUARION-UNITS)
        U::Mermaid => UnitSetting {
            cost: 2,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Fortify, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        // v123 (AQUARION-UNIT-47: id, 10 HP, 3 stars from 05ade18c; AQUARION-UNITS card: 2/1, range 2, Dash Fortify)
        U::MermaidArcher => UnitSetting {
            cost: 3,
            attack: 2.0,
            movement: 1,
            defense: 1.0,
            range: 2,
            health: 10.0,
            skills: skills![S::Dash, S::Fortify, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        // v123 (AQUARION-UNITS-49-52: ids by HP in 9906f7da, 15 / 5 / 10 / 20; AQUARION-UNITS card stats)
        // price 3: MERMAID-DEFENDER-PRICE (game 6 p9 star rows, n=4); the v123 card says 8, a split kept as a test item
        U::MermaidDefender => UnitSetting {
            cost: 3,
            attack: 1.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Fortify, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        U::MermaidCloak => UnitSetting {
            cost: 8,
            attack: 2.0,
            movement: 2,
            defense: 0.5,
            range: 1,
            health: 5.0,
            skills: skills![S::Hide, S::Stiff, S::Infiltrate, S::Dash, S::Scout, S::Creep, S::Static, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        // no Aquarion card seen: the Dagger's stats, amphibious (9906f7da t19: three spawn on water at 10 HP)
        U::MermaidDagger => UnitSetting {
            cost: 2,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Surprise, S::Independent, S::Static, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        // card skills Stiff, Tentacles, Static; Tentacles: actions/units.rs tentacles_after_step (TENTACLES)
        U::Jelly => UnitSetting {
            cost: 8,
            attack: 2.0,
            movement: 2,
            defense: 2.0,
            range: 1,
            health: 20.0,
            skills: skills![S::Stiff, S::Static, S::Water],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        U::Swordsmaid => UnitSetting {
            cost: 5,
            attack: 3.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Dash, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        U::Shark => UnitSetting {
            cost: 8,
            attack: 3.5,
            movement: 3,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Dash, S::Surprise, S::Water],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },
        U::Tridention => UnitSetting {
            cost: 8,
            attack: 2.5,
            movement: 2,
            defense: 1.0,
            range: 2,
            health: 10.0,
            skills: skills![S::Dash, S::Persist, S::Amphibious],
            tribe_type: TribeType::Aquarion,
            ..Default::default()
        },

        // Polaris
        U::Gaami => UnitSetting {
            cost: 10,
            is_super: true,
            attack: 4.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 30.0,
            skills: skills![S::AutoFreeze, S::FreezeArea, S::Static],
            tribe_type: TribeType::Polaris,
            ..Default::default()
        },
        U::IceArcher => UnitSetting {
            cost: 3,
            is_super: false,
            attack: 1.0,
            movement: 1,
            defense: 1.0,
            range: 2,
            health: 10.0,
            skills: skills![S::Dash, S::Freeze, S::Fortify, S::Stiff],
            tribe_type: TribeType::Polaris,
            ..Default::default()
        },
        U::IceFortress => UnitSetting {
            cost: 15,
            is_super: false,
            attack: 4.0,
            movement: 1,
            defense: 3.0,
            range: 2,
            health: 20.0,
            skills: skills![S::Skate, S::Scout, S::Escape, S::Static],
            tribe_type: TribeType::Polaris,
            ..Default::default()
        },
        U::Mooni => UnitSetting {
            cost: 5,
            is_super: false,
            attack: 0.0,
            movement: 1,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Skate, S::AutoFreeze, S::Stiff], // v123: no Static (C29b)
            tribe_type: TribeType::Polaris,
            ..Default::default()
        },
        U::BattleSled => UnitSetting {
            cost: 5,
            is_super: false,
            attack: 3.0,
            movement: 2,
            defense: 2.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Escape, S::Dash, S::Skate],
            tribe_type: TribeType::Polaris,
            ..Default::default()
        },

        // Cymanti
        U::Mantis => UnitSetting {
            cost: 5,
            is_super: false,
            attack: 3.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Dash, S::Creep],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Centipede => UnitSetting {
            cost: 10,
            is_super: true,
            attack: 4.0,
            movement: 2,
            defense: 3.0,
            range: 1,
            health: 20.0,
            skills: skills![S::Dash, S::Creep, S::Eat, S::Static],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Segment => UnitSetting {
            cost: 10,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            skills: skills![
                S::Independent,
                S::Creep,
                S::Explode,
                S::Dash,
                S::Stiff,
                S::Static
            ],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Doomux => UnitSetting {
            cost: 10,
            attack: 3.5,
            movement: 3,
            defense: 2.0,
            range: 1,
            health: 20.0,
            skills: skills![S::Dash, S::Creep, S::Explode, S::Static],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Shaman => UnitSetting {
            cost: 10,
            attack: 1.0,
            movement: 1,
            defense: 1.0,
            range: 1,
            health: 10.0,
            skills: skills![S::Convert, S::Swarm], // v123: no Static (C29b)
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Kiton => UnitSetting {
            cost: 3,
            attack: 1.0,
            movement: 1,
            defense: 3.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Poison, S::Creep],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Hexapod => UnitSetting {
            cost: 3,
            attack: 3.0,
            movement: 2,
            defense: 1.0,
            range: 1,
            health: 5.0,
            skills: skills![S::Dash, S::Escape, S::Creep, S::Sneak],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Raychi => UnitSetting {
            cost: 5,
            attack: 3.0,
            movement: 3,
            defense: 2.0,
            range: 1,
            health: 10.0,
            is_unique: true,
            skills: skills![S::Dash, S::Water],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Boomchi => UnitSetting {
            cost: 5,
            attack: 3.0,
            movement: 2,
            defense: 3.0,
            range: 1,
            health: 10.0,
            is_unique: true,
            skills: skills![S::Dash, S::Explode, S::Stiff, S::Amphibious],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Phychi => UnitSetting {
            cost: 3,
            attack: 0.7,
            movement: 2,
            defense: 1.0,
            range: 2,
            health: 5.0,
            skills: skills![S::Dash, S::Fly, S::Poison, S::Surprise, S::DoubleAttack],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Exida => UnitSetting {
            cost: 8,
            attack: 3.0,
            movement: 1,
            defense: 1.0,
            range: 3,
            health: 10.0,
            skills: skills![S::Poison, S::Splash, S::Creep],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::LivingIsland => UnitSetting {
            cost: 20,
            attack: 4.0,
            movement: 2,
            defense: 4.0,
            range: 1,
            health: 20.0,
            is_super: false,
            skills: skills![S::Water, S::Algae, S::Stomp, S::Poison, S::Static],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::InsectEgg => UnitSetting {
            cost: 0,
            attack: 2.0,
            movement: 0,
            defense: 3.0,
            range: 1,
            health: 10.0,
            is_super: false,
            skills: skills![S::Grow, S::Explode, S::Static, S::Stiff],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Larva => UnitSetting {
            cost: 0,
            attack: 2.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            is_super: false,
            skills: skills![
                S::Dash,
                S::Creep,
                S::Surprise,
                S::Independent,
                S::Static,
                S::Grow
            ],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },
        U::Moth => UnitSetting {
            cost: 5,
            attack: 2.0,
            movement: 2,
            defense: 2.0, // v123 fit (MOTH-V123: at least 1.6)
            range: 1,
            health: 10.0,
            is_super: false,
            skills: skills![
                S::Fly,
                S::Dash,
                S::Sneak,
                S::Infiltrate,
                S::Poison,
                S::Static,
                S::Stiff,
                S::Surprise, // v123 (MOTH-V123): its attack draws no retaliation
                S::Explode   // v123 (MOTH-V123): explodes like a Boomchi (6e1bf8e0 t11 #1674)
            ],
            tribe_type: TribeType::Cymanti,
            ..Default::default()
        },

        // Elyrion
        U::DragonEgg => UnitSetting {
            cost: 10,
            attack: -1.0,
            movement: 1,
            defense: 2.0,
            range: 1,
            health: 10.0,
            is_super: true,
            skills: skills![S::Grow, S::Fortify, S::Static, S::Stiff],
            tribe_type: TribeType::Elyrion,
            ..Default::default()
        },
        U::BabyDragon => UnitSetting {
            cost: 10,
            attack: 3.0,
            movement: 2,
            defense: 3.0,
            range: 1,
            health: 15.0,
            is_super: true,
            skills: skills![S::Grow, S::Dash, S::Fly, S::Escape, S::Scout, S::Static],
            tribe_type: TribeType::Elyrion,
            ..Default::default()
        },
        U::FireDragon => UnitSetting {
            cost: 10,
            attack: 4.0,
            movement: 3,
            defense: 3.0,
            range: 2,
            health: 20.0,
            is_super: true,
            skills: skills![S::Dash, S::Fly, S::Splash, S::Scout, S::Static],
            tribe_type: TribeType::Elyrion,
            ..Default::default()
        },
        U::Polytaur => UnitSetting {
            cost: 2,
            attack: 3.0,
            movement: 1,
            defense: 1.0,
            range: 1,
            health: 15.0,
            skills: skills![S::Dash, S::Fortify, S::Independent, S::Static],
            tribe_type: TribeType::Elyrion,
            ..Default::default()
        },
    }
}

/// Check if a unit type has a specific skill
pub fn has_skill(unit_type: UnitType, skill: SkillType) -> bool {
    get_unit_setting(unit_type).skills.contains(&skill)
}

/// Get super unit type for a tribe
pub fn get_super_unit(tribe_type: TribeType) -> UnitType {
    match tribe_type {
        TribeType::Polaris => UnitType::Gaami,
        TribeType::Aquarion => UnitType::Crab,
        TribeType::Elyrion => UnitType::DragonEgg,
        TribeType::Cymanti => UnitType::Centipede,
        _ => UnitType::Giant,
    }
}
