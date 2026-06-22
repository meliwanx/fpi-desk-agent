/** Plugin management types */

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  source: "builtin" | "global" | "project";
  skills_count: number;
  mcp_count: number;
}

export interface PluginDetail extends PluginInfo {
  skills: Array<{ name: string; description: string }>;
  connector_ids: string[];
}

export interface PluginsStatusResponse {
  plugins: Record<string, PluginInfo>;
}

export interface SkillInfo {
  name: string;
  description: string;
  display_name?: string | null;
  short_description?: string | null;
  location: string;
  source: "bundled" | "plugin" | "project";
  scope?: "system" | "admin" | "user" | "repo" | "project" | "external" | "plugin" | string | null;
  source_path?: string | null;
  allow_implicit_invocation?: boolean;
  tool_dependencies?: Array<Record<string, unknown>>;
  metadata_path?: string | null;
  enabled: boolean;
}

// ─── Store (proxied from skillsmp.com) ─────────────────────────────────

export interface StoreSkill {
  id: string;
  name: string;
  author: string;
  description: string;
  githubUrl: string;
  skillUrl: string;
  stars: number;
  updatedAt: number;
}

export interface StoreSearchResponse {
  success: boolean;
  data: {
    skills: StoreSkill[];
    pagination: {
      page: number;
      limit: number;
      total: number;
      totalPages: number;
      hasNext: boolean;
      hasPrev: boolean;
      totalIsExact?: boolean;
    };
    filters?: Record<string, unknown>;
  };
  meta?: Record<string, unknown>;
}
