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
  provider?: string | null;
  model?: string;
  anthropic_api_key?: string | null;
  openai_api_key?: string | null;
  openai_base_url?: string | null;
  telegram_configured?: boolean;
  telegram_allowed_users?: string | null;
  whatsapp_configured?: boolean;
  whatsapp_connected?: boolean;
  whatsapp_phone_number?: string | null;
  whatsapp_allowed_users?: string | null;
  jina_api_key?: string | null;
  ha_configured?: boolean;
  conversation_model?: string;
  routine_model?: string;
  timezone?: string | null;
  note_detail_level?: string;
  members?: string[];
  members_with_passwords?: string[];
  admin_members?: string[];
}
