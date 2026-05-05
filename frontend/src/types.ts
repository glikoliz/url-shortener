export interface Link {
  id: number;
  original_url: string;
  short_code: string;
  short_url: string;
  clicks: number;
  created_at: string;
  expires_at: string | null;
  user_id: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
}

export interface SSEEvent {
  type: 'link_created' | 'link_deleted' | 'link_updated';
  link?: Link;
  short_code?: string;
  clicks?: number;
  reason?: string;
}

export interface Click {
  id: number;
  clicked_at: string;
  ip_address: string | null;
  user_agent: string | null;
  referer: string | null;
  country: string | null;
  is_unique: boolean;
}

export interface LinkStats {
  total_clicks: number;
  unique_clicks: number;
  unique_ips: number;
  clicks_by_day: Array<{ date: string; clicks: number }>;
  top_countries: Array<{ country: string | null; clicks: number }>;
  top_referers: Array<{ referer: string | null; clicks: number }>;
  granularity?: string;
}

export interface ClicksResponse {
  items: Click[];
  total: number;
}
