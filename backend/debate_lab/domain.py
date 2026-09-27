"""Validated public contracts. Model output is data, never a controller command."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, model_validator

DEFAULT_MODELS = {'Alpha':'gpt-oss:20b','Bravo':'qwen3:30b-a3b-thinking-2507-q4_K_M','Charlie':'gemma4:31b-mlx','Judge':'gemma4:31b-mlx'}
ACTIVE = {'PREPARING','INGESTING','RUNNING','JUDGING','PAUSING','STOPPING'}
TERMINAL = {'COMPLETED','CANCELED'}
TRANSITIONS = {
 'start': {'DRAFT','READY'},
 'upgrade-resume': {'PAUSED','FAILED_RECOVERABLE','READY'}, 'pause': {'INGESTING','RUNNING','JUDGING'},
 'resume': {'PAUSED','FAILED_RECOVERABLE','READY'},
 'restart': {'DRAFT','READY','RUNNING','INGESTING','PAUSED','AWAITING_USER','JUDGING','COMPLETED','CANCELED','FAILED_RECOVERABLE'},
 'stop-and-judge': {'DRAFT','READY','INGESTING','RUNNING','PAUSED','AWAITING_USER','FAILED_RECOVERABLE','JUDGING'},
 'cancel': {'DRAFT','READY','INGESTING','RUNNING','PAUSED','AWAITING_USER','FAILED_RECOVERABLE','JUDGING'},
}
for _action in ('pause','restart','cancel'):
    TRANSITIONS[_action].add('PREPARING')
class Settings(BaseModel):
    execution_policy: Literal['fixed','completion'] = 'completion'
    policy_version: int = Field(1, ge=1, le=1)
    models: dict[str,str] = Field(default_factory=lambda:DEFAULT_MODELS.copy())
    turn_limit: int = Field(12, ge=4, le=100)
    active_minutes: float = Field(15, gt=0, le=240)
    ingestion_tokens: int = Field(60000, ge=1024, le=10000000)
    debate_tokens: int = Field(120000, ge=1024, le=10000000)
    judgment_tokens: int = Field(32000, ge=1024, le=1000000)
    context_tokens: int = Field(16384, ge=2048, le=131072)
    max_context_tokens: int = Field(131072, ge=2048, le=131072)
    output_tokens: int = Field(8192, ge=128, le=16384)
    search_enabled: bool = False
    search_limit: int = Field(3, ge=1, le=20)
    @model_validator(mode='after')
    def valid(self):
        if self.turn_limit % 2: raise ValueError('Turn total must be even.')
        if set(self.models) != set(DEFAULT_MODELS) or any(not x.strip() for x in self.models.values()): raise ValueError('Assign all four roles.')
        if self.max_context_tokens < self.context_tokens: raise ValueError('Maximum context must be at least the starting context.')
        if self.output_tokens >= self.context_tokens: raise ValueError('Output allowance must be smaller than context.')
        return self
class NewSession(BaseModel):
    proposition: str = Field('', max_length=4000)
    preparation_mode: Literal['guided','prepared'] | None = None
    alpha_position: str = Field('', max_length=4000)
    bravo_position: str = Field('', max_length=4000)
    settings: Settings = Field(default_factory=Settings)
    @model_validator(mode='after')
    def subject(self):
        if self.preparation_mode != 'guided' and len(self.proposition.strip()) < 3:
            raise ValueError('Provide a subject, or choose guided preparation.')
        return self

class DebateBrief(BaseModel):
    question: str = Field('', max_length=2000)
    background: str = Field('', max_length=2000)
    scope: str = Field('', max_length=1500)
    definitions: str = Field('', max_length=1500)
    assumptions: str = Field('', max_length=1500)
    intended_resolution: str = Field('', max_length=1500)
    alpha_position: str = Field('', max_length=2000)
    bravo_position: str = Field('', max_length=2000)
    position_rationale: str = Field('', max_length=1500)
    evidence_coverage: str = Field('', max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=20)

class PreparationQuestion(BaseModel):
    question: str = Field(max_length=700)
    options: list[str] = Field(default_factory=list, max_length=4)
    recommendation: str = Field('', max_length=700)

class EvidenceGap(BaseModel):
    needed: str = Field(max_length=700)
    reason: str = Field(max_length=700)
    where_to_find: str = Field(max_length=1000)
    usefulness: str = Field(max_length=700)

class PreparationOutput(BaseModel):
    interpretation: str = Field(max_length=2500)
    suggested_questions: list[str] = Field(default_factory=list, max_length=3)
    questions: list[PreparationQuestion] = Field(default_factory=list, max_length=3)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list, max_length=8)
    brief: DebateBrief

class SourceNote(BaseModel):
    summary: str = Field(min_length=1,max_length=1800)
    uncertainty: list[str] = Field(default_factory=list,max_length=8)
    blocking_question: str = Field('',max_length=700)
class Command(BaseModel):
    command: Literal['start','pause','resume','restart','stop-and-judge','cancel','upgrade-resume']
    expected_revision: int
    idempotency_key: str = Field(min_length=8, max_length=100)
class Claim(BaseModel):
    text: str = Field(max_length=3000)
    references: list[str] = Field(default_factory=list, max_length=30)
    status: Literal['unverified','challenged','accepted','unresolved'] = 'unverified'
class TurnOutput(BaseModel):
    action: Literal['argument','request_information','search','retrieve','surrender']
    public_text: str = Field(min_length=1, max_length=16000)
    claims: list[Claim] = Field(default_factory=list, max_length=30)
    concessions: list[str] = Field(default_factory=list, max_length=20)
    question: str = Field('', max_length=1500)
    reason: str = Field('', max_length=1500)
    query: str = Field('', max_length=300)
    requested_ids: list[str] = Field(default_factory=list, max_length=8)
class EvidenceOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=12000)
    uncertainty: list[str] = Field(default_factory=list, max_length=30)
    blocking_question: str = Field('', max_length=1500)
class Scores(BaseModel):
    evidence: int = Field(ge=0,le=5)
    logic: int = Field(ge=0,le=5)
    relevance: int = Field(ge=0,le=5)
    engagement: int = Field(ge=0,le=5)
class Verdict(BaseModel):
    outcome: Literal['Alpha wins','Bravo wins','tie','inconclusive']
    reason: str
    justification: str
    scores: dict[str,Scores]
    references: list[str]
    supported_claims: list[str]
    unsupported_claims: list[str]
    decisive_objections: list[str]
    concessions: list[str]
    limitations: list[str]
    surrender_confirmed: bool = False
    requested_ids: list[str] = Field(default_factory=list, max_length=8)
    @model_validator(mode='after')
    def roles(self):
        if set(self.scores) != {'Alpha','Bravo'}: raise ValueError('Scores required for Alpha and Bravo.')
        return self

def schedule(total:int):
    if total < 4 or total % 2: raise ValueError('Choose an even total of at least four.')
    return [{'speaker':'Alpha' if n%2==0 else 'Bravo','phase':'opening' if n<2 else 'closing' if n>=total-2 else 'rebuttal','ordinal':n+1} for n in range(total)]

def change_turns(s:dict,total:int):
    schedule(total)
    if s['state'] not in {'DRAFT','PAUSED'}: raise ValueError('Edit the turn total before starting or while paused.')
    if s['closing_started']: raise ValueError('Closing statements have already begun.')
    n=len(s['turns'])
    minimum=max(4, n+2+(n%2))
    if total<minimum: raise ValueError(f'Preserving completed turns and paired rebuttals requires at least {minimum} turns.')
    s['settings']['turn_limit']=total
    s['schedule']=schedule(total)

class HistoryItem(BaseModel):
    turn_id: str
    speaker: Literal['Alpha','Bravo']
    position: str = Field(max_length=900)
    objections: list[str] = Field(default_factory=list,max_length=10)
    unresolved: list[str] = Field(default_factory=list,max_length=10)
    covered_claims: list[int]
    covered_concessions: list[int]
class HistorySummary(BaseModel):
    items: list[HistoryItem] = Field(min_length=1,max_length=2)
