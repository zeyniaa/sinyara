export type Risk = 'high' | 'verify' | 'low' | 'insufficient';
export type CheckStatus = 'done' | 'limited' | 'unavailable' | 'inconclusive' | 'skipped';
export interface AudioInput { name: string; base64: string }
export interface CaseInput { message: string; urls: string[]; audio?: AudioInput }
export interface Evidence { id: string; source: 'message' | 'url' | 'audio' | 'context'; quote: string; explanation: string; indicator: string; start?: number; end?: number }
export interface Check { key: string; title: string; status: CheckStatus; detail: string }
export interface Result { case_id: string; mode: 'real' | 'simulation'; risk: Risk; summary: string; evidence: Evidence[]; checks: Check[]; limitations: string[]; next_steps: string[]; models: Record<string, string>; created_at: string; revision: number }
export interface CaseAccess { case_id: string; token: string }
export interface Progress { stage: string; detail: string; completed: number; total: number; queue_position?: number }
export interface Snapshot { status: 'created' | 'queued' | 'running' | 'done' | 'error'; progress: Progress; result?: Result; error?: { code: string; message: string } }
export interface Answer { answer: string; evidence_ids: string[]; remaining: number; limited: boolean }
export interface CaseClient {
  createCase(input: CaseInput): Promise<CaseAccess>;
  analyzeCase(access: CaseAccess, onProgress: (p: Progress) => void, signal: AbortSignal): Promise<Result>;
  askFollowup(access: CaseAccess, question: string, context?: string): Promise<Answer>;
  deleteCase(access: CaseAccess): Promise<void>;
}
