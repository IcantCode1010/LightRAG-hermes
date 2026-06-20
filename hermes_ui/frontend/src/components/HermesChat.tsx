import { FormEvent, useEffect, useRef, useState } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageAvatar, MessageContent, MessageHeader } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { api, responseText } from "@/lib/api";
import type { ChatMessage } from "@/types";

export function HermesChat({
  addMessage,
  messages,
}: {
  addMessage: (role: ChatMessage["role"], text: string) => void;
  messages: ChatMessage[];
}) {
  const [draft, setDraft] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const content = contentRef.current;
    if (!content) {
      return;
    }
    content.scrollTop = content.scrollHeight;
  }, [messages, isThinking]);

  useEffect(() => {
    if (!isThinking) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - started) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isThinking]);

  const onScroll = () => {
    const content = contentRef.current;
    if (!content) {
      return;
    }
    const distance = content.scrollHeight - content.scrollTop - content.clientHeight;
    setShowScrollButton(distance > 120);
  };

  async function sendChat(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isThinking) {
      return;
    }
    setDraft("");
    addMessage("user", message);
    setIsThinking(true);
    try {
      const response = await api<unknown>("/api/chat", { method: "POST", body: { message } });
      addMessage("agent", responseText(response, "Hermes returned an empty response."));
    } catch (error) {
      addMessage("system", error instanceof Error ? error.message : String(error));
    } finally {
      setIsThinking(false);
    }
  }

  return (
    <>
      <Conversation>
        <ConversationContent ref={contentRef} onScroll={onScroll}>
          {messages.map((message) => (
            <Message key={message.id} role={message.role}>
              <MessageAvatar role={message.role} />
              <div>
                <MessageHeader role={message.role} />
                <MessageContent>{message.text}</MessageContent>
              </div>
            </Message>
          ))}
          {isThinking && <ChatActivity elapsed={elapsed} />}
        </ConversationContent>
        <ConversationScrollButton
          visible={showScrollButton}
          onClick={() => contentRef.current?.scrollTo({ top: contentRef.current.scrollHeight, behavior: "smooth" })}
        />
      </Conversation>

      <PromptInput onSubmit={sendChat}>
        <PromptInputBody>
          <label className="sr-only" htmlFor="chat-message">
            Message
          </label>
          <PromptInputTextarea
            id="chat-message"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask Hermes anything, or ask about the latest indexed documents."
            required
            value={draft}
          />
        </PromptInputBody>
        <PromptInputFooter>
          <Button disabled={isThinking || !draft.trim()} type="submit">
            <SendHorizonal size={16} />
            Send
          </Button>
        </PromptInputFooter>
      </PromptInput>
    </>
  );
}

function ChatActivity({ elapsed }: { elapsed: number }) {
  let label = "Hermes is thinking";
  if (elapsed >= 20) {
    label = "Hermes is still working";
  } else if (elapsed >= 8) {
    label = "Hermes is checking tools";
  }

  return (
    <div className="chat-activity" aria-live="polite">
      <span className="typing-dots" aria-hidden="true">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </span>
      <span>{label} ({elapsed}s)</span>
    </div>
  );
}
