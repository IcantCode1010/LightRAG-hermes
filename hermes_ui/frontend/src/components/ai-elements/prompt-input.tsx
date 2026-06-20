import * as React from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";

export function PromptInput({ className, ...props }: React.FormHTMLAttributes<HTMLFormElement>) {
  return <form className={cn("prompt-input", className)} {...props} />;
}

export function PromptInputBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("prompt-input-body", className)} {...props} />;
}

export function PromptInputTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <Textarea className="prompt-input-textarea" rows={3} {...props} />;
}

export function PromptInputFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("prompt-input-footer", className)} {...props} />;
}
