from ..models import ScenarioEvent

EVENTS = [
    ScenarioEvent(time=0,title='Scarcity, from the start',description='20 tracks. 12 resources. Every commitment has an opportunity cost.'),
    ScenarioEvent(time=12,title='Evidence before action',description='Initial observation window complete. Capacity follows consequence-weighted evidence.'),
    ScenarioEvent(time=24,title='Intent comes into focus',description='Repeated observations sharpen destination estimates. Eight possibilities remain visible.',track_id='T15'),
    ScenarioEvent(time=32,title='An apparent risk changes course',description='T11 turns toward open water. A lower consequence estimate is not a safety guarantee.',track_id='T11'),
    ScenarioEvent(time=50,title='A turn is not a conclusion',description='T03 briefly deviates. Hysteresis gives the estimate time to settle.',track_id='T03'),
    ScenarioEvent(time=62,title='Persistence makes release explainable',description='Inspect T11’s evidence and audit trail. Release requires every confidence and persistence gate.',track_id='T11'),
    ScenarioEvent(time=66,title='A quiet track becomes relevant',description='T17 changes course near the airport sector. Fresh observations drive reassessment.',track_id='T17'),
    ScenarioEvent(time=76,title='Competing demands emerge',description='T18 and T19 change heading. Scarce resources follow sustained priority advantage.',track_id='T18'),
    ScenarioEvent(time=110,title='Compare the decisions',description='Review exposure against first-come allocation. Both policies saw the same observations.'),
]
