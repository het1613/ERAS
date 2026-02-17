// types.ts
export type CasePriority = "Purple" | "Red" | "Orange" | "Yellow" | "Green";

export interface CaseInfo {
    id: string;
    session_id?: string;
    lat: number;
    lon: number;
    location: string;
    type: string;
    priority: CasePriority;
    weight: number;
    status: "open" | "in_progress" | "resolved";
    reported_at: string;
    updated_at: string;
}
