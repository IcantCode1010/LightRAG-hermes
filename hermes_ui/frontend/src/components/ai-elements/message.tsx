import * as React from "react";
import ReactMarkdown from "react-markdown";
import { Bot, CircleAlert, User } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatRole } from "@/types";

export function Message({
  className,
  role,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { role: ChatRole }) {
  return <article className={cn("message", `message-${role}`, className)} {...props} />;
}

export function MessageAvatar({ role }: { role: ChatRole }) {
  const Icon = role === "user" ? User : role === "system" ? CircleAlert : Bot;
  return (
    <div className={cn("message-avatar", `message-avatar-${role}`)} aria-hidden="true">
      <Icon size={16} />
    </div>
  );
}

export function MessageContent({ children }: { children: string }) {
  return (
    <div className="message-content">
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}

export function MessageHeader({ role }: { role: ChatRole }) {
  return <div className="message-role">{role === "agent" ? "Hermes" : role}</div>;
}
