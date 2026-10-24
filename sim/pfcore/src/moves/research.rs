//! Research move
//!
//! Research a new technology.

use crate::moves::{Move, MoveResult};
use crate::states::GameState;
use crate::types::{MoveType, TechnologyType};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResearchMove {
    pub tech_type: TechnologyType,
}

impl ResearchMove {
    pub fn new(tech: TechnologyType) -> Self {
        Self { tech_type: tech }
    }
}

impl Move for ResearchMove {
    fn move_type(&self) -> MoveType {
        MoveType::Research
    }

    fn execute(&self, state: &mut GameState) -> Result<MoveResult, String> {
        let pov_id = state.settings.current_player_turn_id;

        // Validation
        if let Some(tribe) = state.tribes.get(&pov_id) {
            let tech_cost = crate::functions::get_tech_cost(tribe, self.tech_type);
            if tribe.stars < tech_cost {
                return Err(format!(
                    "Insufficient stars for research: need {} (Cities: {}), have {}",
                    tech_cost,
                    tribe.cities.len(),
                    tribe.stars
                ));
            }
        } else {
            return Err("Tribe not found".to_string());
        }

        // Logic
        let undo = crate::actions::tech::unlock_tech(state, self.tech_type, false)?;
        Ok(MoveResult {
            undo,
            rewards: None,
        })
    }

    fn describe(&self, _state: &GameState) -> String {
        format!("Research {:?}", self.tech_type)
    }

    fn serialize(&self) -> serde_json::Value {
        serde_json::json!({
            "moveType": self.move_type(),
            "type": self.tech_type,
        })
    }

    #[inline]
    fn tech_type(&self) -> Result<TechnologyType, String> {
        Ok(self.tech_type)
    }
}

/// Generate research moves
pub fn generate_research_moves(state: &GameState, moves: &mut Vec<Box<dyn Move>>) {
    let pov_id = state.settings.current_player_turn_id;
    if let Some(tribe) = state.tribes.get(&pov_id) {
        // v123 (ledger TRIBE-TECH-TIERS, TECH-TREE): the researchable list follows the v123 tree, tribe techs
        // included (upstream walked each known tech's `next`, which tribe techs don't inherit: 09a5bf1e t1
        // #126 Polaris with Frostwork could not research Sledding)
        let mut available_techs =
            crate::settings::technology::get_researchable_techs(&tribe.tech_vanilla, tribe.tribe_type);
        // Backward, as upstream: a known tech's prerequisite is researchable too (09a5bf1e t1 #114: Vengir,
        // starting with Smithery, research Mining without Climbing)
        for tech_state in &tribe.tech_vanilla {
            if let Some(req) = crate::settings::technology::get_technology_setting(tech_state.tech_type).requires {
                let resolved = crate::settings::technology::resolve_tech_for_tribe(req, tribe.tribe_type);
                if !available_techs.contains(&resolved) {
                    available_techs.push(resolved);
                }
            }
        }
        available_techs.sort_by_key(|t| *t as i8);

        for tech in available_techs {
            // Check if already discovered
            if tribe.tech_vanilla.iter().any(|t| t.tech_type == tech) {
                continue;
            }

            // Check cost
            let cost = crate::functions::get_tech_cost(tribe, tech);
            if tribe.stars >= cost {
                moves.push(Box::new(ResearchMove::new(tech)));
            }
        }
    }
}
