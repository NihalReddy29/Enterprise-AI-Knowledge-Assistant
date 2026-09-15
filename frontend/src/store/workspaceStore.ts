import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Workspace =
  | { type: 'personal' }
  | { type: 'team'; teamId: number; teamName: string }

interface WorkspaceState {
  workspace: Workspace
  setPersonal: () => void
  setTeam: (teamId: number, teamName: string) => void
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      workspace: { type: 'personal' },
      setPersonal: () => set({ workspace: { type: 'personal' } }),
      setTeam: (teamId, teamName) =>
        set({ workspace: { type: 'team', teamId, teamName } }),
    }),
    { name: 'ka-workspace' },
  ),
)

export function workspaceLabel(workspace: Workspace): string {
  return workspace.type === 'personal' ? 'Personal' : workspace.teamName
}
