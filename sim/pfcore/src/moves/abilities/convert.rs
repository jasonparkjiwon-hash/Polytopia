use crate::moves::{Move, MoveResult};
use crate::states::GameState;
use crate::types::{AbilityType, MoveType};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConvertMove {
    pub src_index: i32,
    pub target_index: i32,
}

impl ConvertMove {
    pub fn new(src_index: i32, target_index: i32) -> Self {
        Self {
            src_index,
            target_index,
        }
    }
}

impl Move for ConvertMove {
    fn move_type(&self) -> MoveType {
        MoveType::Ability
    }

    fn execute(&self, state: &mut GameState) -> Result<MoveResult, String> {
        let owner = state.tiles
            .get(&self.src_index)
            .and_then(|t| t._unit_owner_id)
            .unwrap_or(0);

        // v123 (ledger SHAMAN, L3 n=1: e15f392c t9 a Scoutship converted by a Shaman ended at 6 HP): a Shaman's
        // convert also deals its normal damage, with no retaliation; a target it kills is not converted
        let mut pre: Option<crate::actions::UndoCallback> = None;
        let shaman = state.tribes.get(&owner).and_then(|t| {
            t.units.iter().find(|u| u.coords.idx == self.src_index && u.unit_type == crate::types::UnitType::Shaman)
        });
        if let (Some(a), Some(d)) = (shaman, crate::functions::get_true_unit_at(state, self.target_index)) {
            let dmg = crate::actions::units::calculate_combat(
                crate::functions::get_unit_attack(state, a),
                a.health,
                crate::functions::get_unit_max_health(a),
                crate::functions::get_unit_defense(d),
                d.health,
                crate::functions::get_unit_max_health(d),
                crate::functions::get_defense_bonus(state, d),
            )
            .attack_damage;
            let (d_owner, d_hp) = (d.owner, d.health);
            let d_pos = state.tribes[&d_owner].units.iter().position(|u| u.coords.idx == self.target_index).unwrap();
            let undo_dmg = crate::actions::units::deal_damage(state, d_owner, d_pos, dmg, Some(owner));
            if d_hp - dmg <= 0.0 {
                let a_pos = state.tribes[&owner].units.iter().position(|u| u.coords.idx == self.src_index).unwrap();
                let undo_end = crate::actions::end_unit_turn(state, owner, a_pos);
                return Ok(MoveResult { undo: crate::actions::chain_undos(vec![undo_dmg, undo_end]), rewards: None });
            }
            pre = Some(undo_dmg);
        }

        match crate::actions::units::convert_unit(state, self.src_index, self.target_index) {
            Err(e) => {
                if let Some(p) = pre {
                    p(state);
                }
                Err(e)
            }
            Ok(undo) => {
                let undo: crate::actions::UndoCallback = match pre {
                    Some(p) => crate::actions::chain_undos(vec![p, undo]),
                    None => undo,
                };
                let old_attacked_this_turn = state
                    .tribes
                    .get(&owner)
                    .map(|t| t.attacked_this_turn)
                    .unwrap_or(false);
                if let Some(tribe) = state.tribes.get_mut(&owner) {
                    tribe.attacked_this_turn = true;
                    tribe.conversions += 1; // Track for Converter task
                }
                Ok(MoveResult {
                    undo: Box::new(move |s| {
                        if let Some(t) = s.tribes.get_mut(&owner) {
                            t.attacked_this_turn = old_attacked_this_turn;
                            t.conversions -= 1;
                        }
                        undo(s);
                    }),
                    rewards: None,
                })
            }
        }
    }

    fn describe(&self, _state: &GameState) -> String {
        format!("Convert unit at {}", self.target_index)
    }

    fn serialize(&self) -> serde_json::Value {
        serde_json::json!({
            "moveType": self.move_type(),
            "type": self.ability_type().unwrap(),
            "src": self.src_index,
            "target": self.target_index,
        })
    }

    #[inline]
    fn source_idx(&self) -> Result<usize, String> {
        Ok(self.src_index as usize)
    }

    #[inline]
    fn target_idx(&self) -> Result<usize, String> {
        Ok(self.target_index as usize)
    }

    #[inline]
    fn ability_type(&self) -> Result<AbilityType, String> {
        Ok(AbilityType::Convert)
    }
}
