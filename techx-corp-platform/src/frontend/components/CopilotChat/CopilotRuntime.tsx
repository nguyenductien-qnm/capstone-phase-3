import { useLocalRuntime, type ChatModelAdapter, AssistantRuntimeProvider } from "@assistant-ui/react";
import SessionGateway from "../../gateways/Session.gateway";
import { useMemo } from "react";

export const useCopilotAdapter = (onResponse?: (data: any) => void): ChatModelAdapter => {
  return useMemo(() => ({
    async *run({ messages, abortSignal }: any) {
      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== "user") return;

      const sessionId = SessionGateway.getSession().userId;
      const text = lastMessage.content.map((c: any) => c.text).join(" ");
      
      const res = await fetch("/api/copilot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          user_id: sessionId,
          session_id: sessionId,
          confirmation_token: "" // handle token separately if needed
        }),
        signal: abortSignal,
      });

      const data = await res.json();
      if (onResponse) {
        onResponse(data);
      }
      
      if (data.pendingConfirmation) {
        yield {
          content: [
            { type: "text" as const, text: data.response || "Confirmation required." },
            { type: "text" as const, text: `\n\nPending Action: ${data.pendingConfirmation.humanPrompt}` }
          ],
        };
      } else {
        yield { content: [{ type: "text" as const, text: data.response || "Sorry, no response." }] };
      }
    }
  }), [onResponse]);
};
