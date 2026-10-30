#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BattleStatus {
    ScoutPhase = 0,
    Engaging = 1,
    SecuringLoot = 2,
    CoolDown = 3,
}

impl From<BattleStatus> for u64 {
    fn from(value: BattleStatus) -> Self {
        value as u64
    }
}
