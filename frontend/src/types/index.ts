export type UserRole = "admin" | "user" | string;

export interface User {
  userId?: string | number | null;
  id?: string | number | null;
  username: string;
  role?: UserRole | null;
  status?: number | string | boolean | null;
  token: string;
  avatar?: string | null;
}

export interface CurrentUser {
  userId?: string | number | null;
  id?: string | number | null;
  username: string;
  role?: UserRole | null;
  status?: number | string | boolean | null;
  avatar?: string | null;
}

export interface Session {
  id: string;
  title: string;
  lastTime?: string | null;
}

export type MessageRole = "user" | "assistant";
export type MessageStatus = "done" | "streaming" | "cancelled" | "error";
export type FeedbackValue = "like" | "dislike" | null;

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  thinking?: string;
  thinkingDuration?: number;
  isDeepThinking?: boolean;
  isThinking?: boolean;
  createdAt?: string | null;
  feedback?: FeedbackValue;
  status: MessageStatus;
}

export interface StreamMetaPayload {
  conversationId: string;
  taskId: string;
}

export interface MessageDeltaPayload {
  type?: "response" | "think" | string;
  delta: string;
}

export interface CompletionPayload {
  conversationId?: string;
  messageId?: string | number;
  title?: string;
}
