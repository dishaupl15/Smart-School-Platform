export type RoleName = "ADMIN" | "TEACHER" | "STUDENT";

export interface AuthenticatedUser {
  id: string;
  full_name: string;
  email: string | null;
  username: string | null;
  school_id: string | null;
  school_name: string | null;
  roles: RoleName[];
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthenticatedUser;
}
