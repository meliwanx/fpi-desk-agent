"use client";

import { create } from "zustand";

/** Close overlay panels (activity/artifact/plan-review) when workspace opens. */
function closeOverlayPanels() {
  try {
    const { useActivityStore } = require("@/stores/activity-store");
    useActivityStore.getState().close();
  } catch {
    // store may not be available during SSR
  }
  try {
    const { useArtifactStore } = require("@/stores/artifact-store");
    useArtifactStore.getState().close();
  } catch {
    // store may not be available during SSR
  }
  try {
    const { usePlanReviewStore } = require("@/stores/plan-review-store");
    usePlanReviewStore.getState().close();
  } catch {
    // store may not be available during SSR
  }
}

export interface WorkspaceTodo {
  content: string;
  status: "pending" | "in_progress" | "completed";
  activeForm?: string;
}

export interface WorkspaceFile {
  name: string;
  path: string;
  type: "instructions" | "generated" | "uploaded" | "referenced";
}

export interface WorkspaceAgentTask {
  task_id: string;
  session_id: string;
  title: string;
  agent: string;
  model?: string | null;
  provider_id?: string | null;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  error?: string | null;
}

export interface WorkspaceTaskBatch {
  batch_id: string;
  mode: "sequential" | "parallel";
  tasks: WorkspaceAgentTask[];
}

interface WorkspaceSessionSnapshot {
  todos: WorkspaceTodo[];
  taskBatch: WorkspaceTaskBatch | null;
  workspaceFiles: WorkspaceFile[];
  scratchpadContent: string;
  activeWorkspacePath: string | null;
}

function emptyWorkspaceSnapshot(): WorkspaceSessionSnapshot {
  return {
    todos: [],
    taskBatch: null,
    workspaceFiles: [],
    scratchpadContent: "",
    activeWorkspacePath: null,
  };
}

function normalizeWorkspacePath(path: string | null): string | null {
  return path && path !== "." ? path : null;
}

interface WorkspaceStore {
  isOpen: boolean;
  activeSessionId: string | null;
  workspaceBySession: Record<string, WorkspaceSessionSnapshot>;
  /** Per-section collapsed state (false / missing = expanded). */
  collapsedSections: Record<string, boolean>;
  todos: WorkspaceTodo[];
  taskBatch: WorkspaceTaskBatch | null;
  workspaceFiles: WorkspaceFile[];
  scratchpadContent: string;
  /** Current session's workspace directory (set by ChatView on session load). */
  activeWorkspacePath: string | null;

  toggle: () => void;
  open: () => void;
  close: () => void;
  toggleSection: (section: string) => void;
  expandSection: (section: string) => void;
  collapseSection: (section: string) => void;
  setTodos: (todos: WorkspaceTodo[], sessionId?: string | null) => void;
  setTaskBatch: (batch: WorkspaceTaskBatch | null, sessionId?: string | null) => void;
  addWorkspaceFile: (file: WorkspaceFile, sessionId?: string | null) => void;
  setWorkspaceFiles: (files: WorkspaceFile[], sessionId?: string | null) => void;
  setScratchpadContent: (content: string, sessionId?: string | null) => void;
  setActiveWorkspacePath: (path: string | null, sessionId?: string | null) => void;
  resetForSession: (sessionId: string) => void;
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  isOpen: false,
  activeSessionId: null,
  workspaceBySession: {},
  collapsedSections: {
    progress: true,
    files: true,
    context: true,
  },
  todos: [],
  taskBatch: null,
  workspaceFiles: [],
  scratchpadContent: "",
  activeWorkspacePath: null,

  toggle: () => {
    const willOpen = !get().isOpen;
    if (willOpen) closeOverlayPanels();
    set({ isOpen: willOpen });
  },
  open: () => {
    closeOverlayPanels();
    set({ isOpen: true });
  },
  close: () => set({ isOpen: false }),

  toggleSection: (section) =>
    set((s) => ({
      collapsedSections: {
        ...s.collapsedSections,
        [section]: !s.collapsedSections[section],
      },
    })),

  expandSection: (section) =>
    set((s) => ({
      collapsedSections: {
        ...s.collapsedSections,
        [section]: false,
      },
    })),

  collapseSection: (section) =>
    set((s) => ({
      collapsedSections: {
        ...s.collapsedSections,
        [section]: true,
      },
    })),

  setTodos: (todos, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      if (!targetSessionId) {
        return { todos, ...(todos.length > 0 ? { isOpen: true } : {}) };
      }

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, todos },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, todos, ...(todos.length > 0 ? { isOpen: true } : {}) };
    }),

  setTaskBatch: (taskBatch, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      if (!targetSessionId) {
        return { taskBatch, ...(taskBatch ? { isOpen: true } : {}) };
      }

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, taskBatch },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, taskBatch, ...(taskBatch ? { isOpen: true } : {}) };
    }),

  addWorkspaceFile: (file, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      if (!targetSessionId) {
        if (s.workspaceFiles.some((f) => f.path === file.path)) return s;
        return { workspaceFiles: [...s.workspaceFiles, file] };
      }

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      if (prev.workspaceFiles.some((f) => f.path === file.path)) return s;
      const workspaceFiles = [...prev.workspaceFiles, file];
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, workspaceFiles },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, workspaceFiles };
    }),

  setWorkspaceFiles: (files, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      if (!targetSessionId) return { workspaceFiles: files };

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, workspaceFiles: files },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, workspaceFiles: files };
    }),

  setScratchpadContent: (content, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      if (!targetSessionId) return { scratchpadContent: content };

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, scratchpadContent: content },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, scratchpadContent: content };
    }),

  setActiveWorkspacePath: (path, sessionId) =>
    set((s) => {
      const targetSessionId = sessionId ?? s.activeSessionId;
      const activeWorkspacePath = normalizeWorkspacePath(path);
      if (!targetSessionId) return { activeWorkspacePath };

      const prev = s.workspaceBySession[targetSessionId] ?? emptyWorkspaceSnapshot();
      const workspaceBySession = {
        ...s.workspaceBySession,
        [targetSessionId]: { ...prev, activeWorkspacePath },
      };
      if (targetSessionId !== s.activeSessionId) return { workspaceBySession };

      return { workspaceBySession, activeWorkspacePath };
    }),

  resetForSession: (sessionId) =>
    set((s) => {
      const snapshot = s.workspaceBySession[sessionId] ?? emptyWorkspaceSnapshot();
      return {
        activeSessionId: sessionId,
        todos: snapshot.todos,
        taskBatch: snapshot.taskBatch,
        workspaceFiles: snapshot.workspaceFiles,
        scratchpadContent: snapshot.scratchpadContent,
        collapsedSections: {
          progress: true,
          files: true,
          context: true,
        },
        activeWorkspacePath: snapshot.activeWorkspacePath,
        isOpen: false,
      };
    }),
}));
