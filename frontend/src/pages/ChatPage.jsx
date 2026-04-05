import { useCallback, useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Flex,
  Heading,
  Progress,
  Stack,
  Text,
  Textarea,
  Tooltip,
} from "@chakra-ui/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import * as api from "../api/client.js";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  /** Same as state but updated synchronously so the next Send always sends the latest id. */
  const conversationIdRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [memoryInfo, setMemoryInfo] = useState(null);
  const [contextUsage, setContextUsage] = useState(null);
  const [err, setErr] = useState("");
  const [listError, setListError] = useState("");
  const [listLoading, setListLoading] = useState(true);
  const bottomRef = useRef(null);

  const refreshConversations = useCallback(async () => {
    setListError("");
    setListLoading(true);
    try {
      const data = await api.listChats();
      setConversations(data.conversations || []);
    } catch (e) {
      const msg = String(e.message || e);
      setListError(msg);
      console.error("listChats failed:", msg);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function newChat() {
    conversationIdRef.current = null;
    setConversationId(null);
    setMessages([]);
    setMemoryInfo(null);
    setContextUsage(null);
    setErr("");
    setQ("");
  }

  async function loadConversation(id) {
    if (loading) return;
    conversationIdRef.current = id;
    setConversationId(id);
    setErr("");
    setMemoryInfo(null);
    setContextUsage(null);
    setQ("");
    try {
      const data = await api.getChatMessages(id);
      conversationIdRef.current = data.conversation_id;
      setConversationId(data.conversation_id);
      const rows = data.messages || [];
      setMessages(
        rows.map((row) => ({
          id: row.id,
          role: row.role,
          content: row.content,
          sources: row.sources || [],
        }))
      );
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  async function removeConversation(id, e) {
    e?.stopPropagation?.();
    try {
      await api.deleteChat(id);
      if (conversationIdRef.current === id || conversationId === id) {
        newChat();
      }
      await refreshConversations();
    } catch (err2) {
      setErr(String(err2.message || err2));
    }
  }

  async function onSend() {
    if (!q.trim() || loading) return;
    const question = q.trim();
    const assistantId = `assistant-${Date.now()}`;
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    setLoading(true);
    setErr("");
    setMemoryInfo(null);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question, sources: [] },
      { id: assistantId, role: "assistant", content: "", sources: [] },
    ]);
    setQ("");
    try {
      const cid = conversationIdRef.current;
      const data = await api.chatStream(question, history, cid, {
        onStart: (event) => {
          const newId = event.conversation_id || null;
          conversationIdRef.current = newId;
          setConversationId(newId);
        },
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: `${msg.content || ""}${delta}` }
                : msg
            )
          );
        },
      });
      const newId = data.conversation_id || null;
      conversationIdRef.current = newId;
      setConversationId(newId);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantId
            ? {
                ...msg,
                content: data.answer || msg.content || "",
                sources: data.sources || [],
              }
            : msg
        )
      );
      setMemoryInfo(data.memory || null);
      setContextUsage(data.context_usage ?? null);
      await refreshConversations();
    } catch (e) {
      setMessages((prev) =>
        prev.filter((msg) => !(msg.id === assistantId && !msg.content))
      );
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const bd = contextUsage?.breakdown;
  const segSys = bd?.system ?? 0;
  const segHist = bd?.history ?? 0;
  const segDoc = bd?.documents_and_question ?? 0;
  const segSum = segSys + segHist + segDoc || 1;
  const markdownSx = {
    fontSize: "sm",
    lineHeight: "1.6",
    "& p": { mb: 3 },
    "& p:last-of-type": { mb: 0 },
    "& ul, & ol": { paddingLeft: "1.25rem", marginBottom: "0.75rem" },
    "& li": { marginBottom: "0.25rem" },
    "& strong": { fontWeight: 800 },
    "& em": { fontStyle: "italic" },
    "& code": {
      fontFamily: "mono",
      fontSize: "0.85em",
      bg: "gray.50",
      px: 1,
      py: "1px",
    },
    "& pre": {
      whiteSpace: "pre-wrap",
      overflowX: "auto",
      bg: "gray.50",
      border: "1px solid",
      borderColor: "black",
      p: 3,
      marginBottom: "0.75rem",
    },
    "& pre code": {
      bg: "transparent",
      p: 0,
      fontSize: "0.9em",
    },
    "& a": {
      textDecoration: "underline",
    },
    "& blockquote": {
      borderLeft: "2px solid",
      borderColor: "gray.400",
      pl: 3,
      color: "gray.700",
      marginBottom: "0.75rem",
    },
  };

  return (
    <Flex
      gap={6}
      align="stretch"
      flexWrap={{ base: "wrap", lg: "nowrap" }}
      h="100%"
      maxH="100%"
      minH="0"
      overflow="hidden"
    >
      <Box
        border="1px solid"
        borderColor="black"
        minW="200px"
        maxW="260px"
        flex="0 0 auto"
        p={3}
        maxH={{ base: "320px", lg: "100%" }}
        overflowY="auto"
        bg="white"
      >
        <Stack spacing={2}>
          <Button variant="solid" size="sm" w="100%" onClick={newChat}>
            New chat
          </Button>
          {listLoading && (
            <Text fontSize="xs" color="gray.600">
              Loading chats…
            </Text>
          )}
          {listError && (
            <Box border="1px solid" borderColor="red.600" p={2} bg="red.50" fontSize="xs">
              <Text fontWeight="700" mb={1}>
                Could not load chat list
              </Text>
              <Text mb={2}>{listError}</Text>
              <Button size="xs" variant="outline" onClick={() => refreshConversations()}>
                Retry
              </Button>
            </Box>
          )}
          {!listLoading && !listError && conversations.length === 0 && (
            <Text fontSize="xs" color="gray.600">
              No saved chats yet. Send a message to start one.
            </Text>
          )}
          {conversations.map((c) => (
            <Flex
              key={c.id}
              align="center"
              gap={1}
              border="1px solid"
              borderColor={conversationId === c.id ? "black" : "gray.300"}
              p={2}
              cursor="pointer"
              bg={conversationId === c.id ? "gray.100" : "white"}
              onClick={() => loadConversation(c.id)}
            >
              <Text fontSize="xs" flex="1" noOfLines={2} fontWeight="600">
                {c.title || c.id.slice(0, 8)}
              </Text>
              <Button
                size="xs"
                variant="outline"
                px={1}
                minW="24px"
                onClick={(e) => removeConversation(c.id, e)}
                aria-label="Delete"
              >
                ×
              </Button>
            </Flex>
          ))}
        </Stack>
      </Box>

      <Flex
        direction="column"
        gap={6}
        align="stretch"
        flex="1"
        minW="280px"
        minH="0"
        h="100%"
        maxH="100%"
        overflow="hidden"
      >
        <Flex justify="space-between" align="flex-start" flexWrap="wrap" gap={3}>
          <Box>
            <Heading size="md" fontWeight="800" letterSpacing="-0.02em">
              Chat
            </Heading>
            <Text fontSize="sm" color="gray.700" mt={1}>
              {conversationId ? `Current session: …${conversationId.slice(-8)}.` : "New session."} Memory uses a
              ~50k-token window with auto compaction.
            </Text>
          </Box>
        </Flex>

        <Box border="1px solid" borderColor="black" p={3} bg="gray.50">
          <Text fontSize="xs" fontWeight="800" mb={2} textTransform="uppercase">
            Context window (estimated)
          </Text>
          {!contextUsage && (
            <Text fontSize="sm" color="gray.700" mb={2}>
              Send a message to see how much of the ~50k window this turn uses (system + history +
              retrieval + question).
            </Text>
          )}
          {contextUsage && (
            <>
              <Text fontSize="xs" mb={1} color="gray.700">
                Total fill vs {contextUsage.window_tokens?.toLocaleString?.() ?? contextUsage.window_tokens}{" "}
                tokens
              </Text>
              <Progress
                value={Math.min(100, contextUsage.percent_of_window ?? 0)}
                size="sm"
                borderRadius="none"
                border="1px solid"
                borderColor="black"
                bg="white"
                mb={3}
                sx={{ "& > div": { background: "black" } }}
              />
              <Text fontSize="xs" mb={1} color="gray.700">
                Composition (input)
              </Text>
              <Flex
                h="12px"
                border="1px solid"
                borderColor="black"
                mb={2}
                overflow="hidden"
                w="100%"
              >
                <Box
                  w={`${(segSys / segSum) * 100}%`}
                  minW={segSys > 0 ? "3px" : 0}
                  bg="black"
                  title={`System ~${segSys}`}
                />
                <Box
                  w={`${(segHist / segSum) * 100}%`}
                  minW={segHist > 0 ? "3px" : 0}
                  bg="gray.600"
                  title={`History ~${segHist}`}
                />
                <Box
                  w={`${(segDoc / segSum) * 100}%`}
                  minW={segDoc > 0 ? "3px" : 0}
                  bg="gray.400"
                  title={`Retrieval + question ~${segDoc}`}
                />
              </Flex>
              <Flex fontSize="xs" gap={4} flexWrap="wrap" color="gray.800" mb={2}>
                <Text>
                  <Box as="span" display="inline-block" w="8px" h="8px" bg="black" mr={1} verticalAlign="middle" />
                  System ~{segSys}
                </Text>
                <Text>
                  <Box as="span" display="inline-block" w="8px" h="8px" bg="gray.600" mr={1} verticalAlign="middle" />
                  History ~{segHist}
                </Text>
                <Text>
                  <Box as="span" display="inline-block" w="8px" h="8px" bg="gray.400" mr={1} verticalAlign="middle" />
                  Retrieval + question ~{segDoc}
                </Text>
              </Flex>
              <Text fontSize="sm" fontWeight="700">
                ~{(contextUsage.estimated_input_tokens ?? 0).toLocaleString()} /{" "}
                {(contextUsage.window_tokens ?? 0).toLocaleString()} tok (
                {contextUsage.percent_of_window ?? 0}% of window ·{" "}
                {contextUsage.percent_of_input_budget ?? 0}% of input budget)
              </Text>
              <Text fontSize="xs" color="gray.600" mt={1}>
                ~{(contextUsage.reserved_output_tokens ?? 0).toLocaleString()} tok reserved for output · free ~{" "}
                {(contextUsage.free_tokens_estimate ?? 0).toLocaleString()} (estimated). Heuristic: ~4 chars ≈ 1
                token.
              </Text>
              {bd?.history_tokens_before_compact != null &&
                bd.history_tokens_before_compact > (bd?.history ?? 0) && (
                  <Text fontSize="xs" color="gray.600" mt={1}>
                    History before compaction: ~{bd.history_tokens_before_compact} tok → after ~{bd?.history ?? 0}{" "}
                    tok.
                  </Text>
                )}
            </>
          )}
        </Box>

        <Box border="1px solid" borderColor="black" flex="1" minH="0" overflowY="auto" p={4} bg="white">
          <Stack spacing={4}>
            {messages.length === 0 && !loading && (
              <Text fontSize="sm" color="gray.600">
                Ask a question or open a saved chat from the left.
              </Text>
            )}
            {messages.map((m, i) => (
              <Box
                key={m.id ?? `m-${i}`}
                alignSelf={m.role === "user" ? "flex-end" : "flex-start"}
                maxW="85%"
              >
                <Box
                  border="1px solid"
                  borderColor="black"
                  p={3}
                  bg={m.role === "user" ? "gray.100" : "white"}
                >
                  <Box sx={markdownSx}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content || ""}
                    </ReactMarkdown>
                  </Box>
                  {m.role === "assistant" && (m.sources || []).length > 0 && (
                    <Flex mt={3} gap={2} flexWrap="wrap" align="center">
                      {(m.sources || []).map((s, idx) => (
                        <Tooltip
                          key={`${m.id ?? i}-src-${idx}`}
                          hasArrow
                          placement="top-start"
                          openDelay={120}
                          bg="white"
                          color="black"
                          border="1px solid"
                          borderColor="black"
                          borderRadius="none"
                          p={3}
                          maxW="420px"
                          label={
                            <Box>
                              <Text fontSize="xs" fontWeight="700" mb={1}>
                                {s.source}
                                {s.page != null ? ` · page ${s.page + 1}` : ""}
                              </Text>
                              <Text fontSize="xs" whiteSpace="pre-wrap">
                                {s.snippet}
                              </Text>
                            </Box>
                          }
                        >
                          <Text
                            fontSize="xs"
                            textDecoration="underline"
                            cursor="help"
                            width="fit-content"
                          >
                            [{idx + 1}]
                          </Text>
                        </Tooltip>
                      ))}
                    </Flex>
                  )}
                </Box>
              </Box>
            ))}
            {loading && (
              <Text fontSize="sm" color="gray.600">
                Streaming…
              </Text>
            )}
            {err && (
              <Box border="1px solid" borderColor="red.600" p={3} bg="red.50">
                <Text fontSize="sm">{err}</Text>
              </Box>
            )}
            {memoryInfo?.compacted && (
              <Box border="1px solid" borderColor="black" p={3} bg="gray.50" fontSize="xs">
                <Text fontWeight="800" mb={1}>
                  Memory compaction
                </Text>
                <Text>
                  Earlier turns were summarized to stay within the ~50k context window
                  {memoryInfo.summarized_turns != null
                    ? ` (${memoryInfo.summarized_turns} turns summarized, ${memoryInfo.kept_turns ?? "?"} kept).`
                    : "."}
                </Text>
              </Box>
            )}
            <div ref={bottomRef} />
          </Stack>
        </Box>

        <Box
          border="1px solid"
          borderColor="black"
          p={4}
          bg="white"
          position="sticky"
          bottom={0}
          zIndex={1}
        >
          <Stack spacing={3}>
            <Textarea
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Message…"
              minH="80px"
              borderRadius="none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !loading) {
                  e.preventDefault();
                  onSend();
                }
              }}
            />
            <Button
              variant="solid"
              alignSelf="flex-start"
              onClick={onSend}
              isLoading={loading}
              loadingText="Answering"
              isDisabled={loading}
            >
              Send
            </Button>
          </Stack>
        </Box>
      </Flex>
    </Flex>
  );
}
