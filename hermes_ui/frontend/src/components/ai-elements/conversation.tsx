import * as React from "react";
import { ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Conversation({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("conversation", className)} {...props} />;
}

export function ConversationContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("conversation-content", className)} {...props} />;
}

export function ConversationScrollButton({
  visible,
  onClick,
}: {
  visible: boolean;
  onClick: () => void;
}) {
  if (!visible) {
    return null;
  }
  return (
    <Button
      aria-label="Scroll to latest message"
      className="conversation-scroll-button"
      onClick={onClick}
      size="icon"
      type="button"
      variant="secondary"
    >
      <ArrowDown size={16} />
    </Button>
  );
}
