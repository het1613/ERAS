// types.ts
export type CasePriority = "Purple" | "Red" | "Orange" | "Yellow" | "Green";

export interface CaseInfo {
    id: string;
    priority: CasePriority;
    type: string;
    location: string;
    reportedTime: string;
    lat?: number;
    lng?: number;
}