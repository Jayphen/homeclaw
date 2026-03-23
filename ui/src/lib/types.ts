/** Constrained types mirroring Python Literal definitions. */
export type ProviderType = "anthropic" | "openai";
export type WebReadProvider = "jina" | "tavily";
export type ProviderMode = "simple" | "advanced";
export type NoteDetailLevel = "minimal" | "normal" | "detailed";
export type InteractionType = "call" | "message" | "meetup" | "other";

/** Setup status returned by GET /api/setup/status.
 *
 * Base fields are always present (even unauthenticated).
 * Extended fields require auth and may be undefined before login.
 */
export interface SetupStatus {
  // Always present (base)
  version?: string;
  has_password: boolean;
  needs_setup_token?: boolean;
  provider_configured: boolean;
  has_member_accounts?: boolean;

  // Present after auth
  provider?: ProviderType | null;
  model?: string;
  anthropic_api_key?: string | null;
  anthropic_base_url?: string | null;
  openai_api_key?: string | null;
  openai_base_url?: string | null;
  fast_provider?: ProviderType | null;
  fast_api_key?: string | null;
  fast_base_url?: string | null;
  vision_provider?: ProviderType | null;
  vision_api_key?: string | null;
  vision_base_url?: string | null;
  telegram_configured?: boolean;
  telegram_allowed_users?: string | null;
  whatsapp_configured?: boolean;
  whatsapp_connected?: boolean;
  whatsapp_phone_number?: string | null;
  whatsapp_allowed_users?: string | null;
  jina_api_key?: string | null;
  tavily_api_key?: string | null;
  web_read_provider?: WebReadProvider | null;
  web_read_fallback?: WebReadProvider | null;
  ha_configured?: boolean;
  conversation_model?: string;
  fast_model?: string;
  vision_model?: string;
  provider_mode?: ProviderMode | null;
  timezone?: string | null;
  note_detail_level?: NoteDetailLevel;
  members?: string[];
  members_with_passwords?: string[];
  admin_members?: string[];
}
