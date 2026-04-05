import { useEffect, useState } from "react";
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Heading,
  Input,
  NumberInput,
  NumberInputField,
  Stack,
  Text,
} from "@chakra-ui/react";
import * as api from "../api/client.js";

export default function SettingsPage() {
  const [chunkSize, setChunkSize] = useState(1000);
  const [chunkOverlap, setChunkOverlap] = useState(150);
  const [topK, setTopK] = useState(4);
  const [embeddingModel, setEmbeddingModel] = useState("nomic-embed-text");
  const [llmModel, setLlmModel] = useState("llama3.2");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const s = await api.getSettings();
        setChunkSize(s.chunk_size);
        setChunkOverlap(s.chunk_overlap);
        setTopK(s.top_k);
        setEmbeddingModel(s.embedding_model);
        setLlmModel(s.llm_model);
      } catch (e) {
        setNote(String(e.message || e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function onSave() {
    setSaving(true);
    setNote("");
    try {
      await api.putSettings({
        chunk_size: Number(chunkSize),
        chunk_overlap: Number(chunkOverlap),
        top_k: Number(topK),
        embedding_model: embeddingModel,
        llm_model: llmModel,
      });
      setNote("Saved. Re-index if you changed the embedding model.");
    } catch (e) {
      setNote(String(e.message || e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack spacing={6} align="stretch">
      <Heading size="md" fontWeight="800" letterSpacing="-0.02em">
        Settings
      </Heading>
      <Text fontSize="sm" color="gray.700">
        Chunking and retrieval parameters; model names must match what Ollama serves locally.
      </Text>
      <Box border="1px solid" borderColor="black" p={4}>
        <Stack spacing={4}>
          <FormControl>
            <FormLabel fontSize="sm" fontWeight="700">
              chunk_size
            </FormLabel>
            <NumberInput
              value={chunkSize}
              onChange={(_, v) => setChunkSize(v)}
              min={100}
              max={8000}
            >
              <NumberInputField borderRadius="none" />
            </NumberInput>
          </FormControl>
          <FormControl>
            <FormLabel fontSize="sm" fontWeight="700">
              chunk_overlap
            </FormLabel>
            <NumberInput
              value={chunkOverlap}
              onChange={(_, v) => setChunkOverlap(v)}
              min={0}
              max={2000}
            >
              <NumberInputField borderRadius="none" />
            </NumberInput>
          </FormControl>
          <FormControl>
            <FormLabel fontSize="sm" fontWeight="700">
              top_k
            </FormLabel>
            <NumberInput value={topK} onChange={(_, v) => setTopK(v)} min={1} max={20}>
              <NumberInputField borderRadius="none" />
            </NumberInput>
          </FormControl>
          <FormControl>
            <FormLabel fontSize="sm" fontWeight="700">
              embedding_model (Ollama)
            </FormLabel>
            <Input
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              borderRadius="none"
            />
          </FormControl>
          <FormControl>
            <FormLabel fontSize="sm" fontWeight="700">
              llm_model (Ollama)
            </FormLabel>
            <Input
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              borderRadius="none"
            />
          </FormControl>
          <Button
            variant="solid"
            alignSelf="flex-start"
            onClick={onSave}
            isLoading={saving || loading}
            loadingText="Saving"
          >
            Save
          </Button>
        </Stack>
      </Box>
      {note && (
        <Box border="1px solid" borderColor="black" p={3} bg="gray.50">
          <Text fontSize="sm">{note}</Text>
        </Box>
      )}
    </Stack>
  );
}
