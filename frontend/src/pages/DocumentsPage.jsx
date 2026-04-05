import { useCallback, useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Flex,
  Heading,
  Input,
  Progress,
  Stack,
  Text,
} from "@chakra-ui/react";
import * as api from "../api/client.js";

const POLL_MS = 450;

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [orphanedIndexes, setOrphanedIndexes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [idx, setIdx] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");
  const [fullReset, setFullReset] = useState(false);
  const pollRef = useRef(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listDocuments();
      setDocuments(data.documents || []);
      setSummary(data.indexed_summary || null);
      setOrphanedIndexes(data.orphaned_indexes || []);
    } catch (e) {
      setMsg(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  async function runJob(startFn) {
    setBusy(true);
    setMsg("");
    setIdx(null);
    setProgress(0);
    setProgressLabel("Starting…");
    stopPoll();

    const applyJob = (job) => {
      setProgress(typeof job.progress === "number" ? job.progress : 0);
      setProgressLabel(job.message || "");
      if (job.status === "completed") {
        setBusy(false);
        setProgress(100);
        setProgressLabel("Done");
        setIdx(job.result || null);
        refresh().catch(() => {});
        if (job.result?.message) {
          setMsg(job.result.message);
        } else if (job.result) {
          setMsg(
            `Indexed ${job.result.chunks ?? 0} chunks, ${job.result.indexed ?? 0} file(s).`
          );
        } else {
          setMsg("Indexing completed.");
        }
      } else if (job.status === "failed") {
        setBusy(false);
        setProgress(0);
        setProgressLabel("");
        setMsg(job.error || "Indexing failed.");
      }
    };

    try {
      const { job_id: jobId } = await startFn();

      const tick = async () => {
        const job = await api.getReindexJob(jobId);
        applyJob(job);
        return job.status;
      };

      const s1 = await tick();
      if (s1 !== "completed" && s1 !== "failed") {
        pollRef.current = setInterval(async () => {
          try {
            const s = await tick();
            if (s === "completed" || s === "failed") stopPoll();
          } catch (e) {
            stopPoll();
            setBusy(false);
            setMsg(String(e.message || e));
          }
        }, POLL_MS);
      }
    } catch (e) {
      setBusy(false);
      setMsg(String(e.message || e));
    }
  }

  async function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    setMsg("");
    try {
      await api.uploadPdf(f);
      await refresh();
      setMsg(`Uploaded: ${f.name}`);
    } catch (err) {
      setMsg(String(err.message || err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  function onReindexAll() {
    runJob(() =>
      api.startReindexJob({ filename: null, reset: fullReset })
    );
  }

  function onReindexOne(name) {
    runJob(() =>
      api.startReindexJob({ filename: name, reset: false })
    );
  }

  async function onDeleteIndex(name) {
    if (!window.confirm(`Delete vectors for ${name}?`)) return;
    setBusy(true);
    setMsg("");
    try {
      const result = await api.deleteDocumentIndex(name);
      await refresh();
      setMsg(
        result.deleted_chunks > 0
          ? `Deleted ${result.deleted_chunks} indexed chunk(s) for ${name}.`
          : `No index was stored for ${name}.`
      );
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteAllIndexes() {
    if (!window.confirm("Delete the entire vector index for every document?")) {
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const result = await api.deleteAllIndexes();
      await refresh();
      setIdx(null);
      setMsg(
        `Deleted ${result.deleted_chunks ?? 0} chunk(s) across ${result.deleted_sources ?? 0} indexed source(s).`
      );
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack spacing={6} align="stretch">
      <Heading size="md" fontWeight="800" letterSpacing="-0.02em">
        Documents
      </Heading>
      <Text fontSize="sm" color="gray.700">
        See which PDFs are currently indexed, how many chunks each one has, and
        remove stale vectors when needed. Enable &quot;Full reset&quot; to wipe
        the vector store before a full re-index.
      </Text>
      <Flex gap={3} flexWrap="wrap">
        <Box border="1px solid" borderColor="black" p={3} minW="180px" bg="white">
          <Text fontSize="xs" textTransform="uppercase" fontWeight="800" mb={1}>
            PDFs
          </Text>
          <Text fontSize="lg" fontWeight="800">
            {summary?.pdf_count ?? documents.length}
          </Text>
        </Box>
        <Box border="1px solid" borderColor="black" p={3} minW="180px" bg="white">
          <Text fontSize="xs" textTransform="uppercase" fontWeight="800" mb={1}>
            Indexed PDFs
          </Text>
          <Text fontSize="lg" fontWeight="800">
            {summary?.indexed_pdf_count ?? 0}
          </Text>
        </Box>
        <Box border="1px solid" borderColor="black" p={3} minW="180px" bg="white">
          <Text fontSize="xs" textTransform="uppercase" fontWeight="800" mb={1}>
            Indexed chunks
          </Text>
          <Text fontSize="lg" fontWeight="800">
            {summary?.indexed_chunk_count ?? 0}
          </Text>
        </Box>
      </Flex>
      <Box border="1px solid" borderColor="black" p={4}>
        <Stack spacing={3}>
          <Input
            type="file"
            accept=".pdf,application/pdf"
            onChange={onFile}
            disabled={busy}
            p={1}
            border="none"
            _focus={{ boxShadow: "none" }}
          />
          <Checkbox
            isChecked={fullReset}
            onChange={(e) => setFullReset(e.target.checked)}
            isDisabled={busy}
            borderColor="black"
            fontSize="sm"
            fontWeight="600"
          >
            Full reset (delete entire index before indexing all PDFs)
          </Checkbox>
          <Button
            variant="solid"
            alignSelf="flex-start"
            onClick={onReindexAll}
            isLoading={busy}
            loadingText="Indexing"
          >
            Index all PDFs
          </Button>
          <Button
            variant="outline"
            alignSelf="flex-start"
            onClick={onDeleteAllIndexes}
            isDisabled={busy || (summary?.indexed_chunk_count ?? 0) === 0}
          >
            Delete all indexes
          </Button>
        </Stack>
      </Box>
      {busy && (
        <Box border="1px solid" borderColor="black" p={4}>
          <Text fontSize="xs" fontWeight="700" mb={2}>
            Indexing
          </Text>
          <Progress
            value={progress}
            size="sm"
            borderRadius="none"
            border="1px solid"
            borderColor="black"
            bg="white"
            sx={{
              "& > div": {
                background: "black",
              },
            }}
          />
          <Text fontSize="sm" mt={2} color="gray.800">
            {Math.round(progress)}% — {progressLabel || "…"}
          </Text>
        </Box>
      )}
      {msg && (
        <Box border="1px solid" borderColor="black" p={3} bg="gray.50">
          <Text fontSize="sm" whiteSpace="pre-wrap">
            {msg}
          </Text>
        </Box>
      )}
      {idx && !idx.message && (
        <Box border="1px solid" borderColor="black" p={3} fontSize="sm">
          <Text fontWeight="700">Last index summary</Text>
          <Text>Chunks: {idx.chunks}</Text>
          <Text>Files: {idx.indexed}</Text>
          {idx.files && (
            <Text mt={1}>Filenames: {idx.files.join(", ")}</Text>
          )}
        </Box>
      )}
      <Box>
        <Text fontWeight="800" mb={2} fontSize="sm">
          Uploaded PDFs
        </Text>
        <Stack spacing={2} border="1px solid" borderColor="black" p={3} bg="white">
          {documents.length === 0 && (
            <Text fontSize="sm" color="gray.600">
              No files yet.
            </Text>
          )}
          {documents.map((doc) => (
            <Box
              key={doc.filename}
              fontSize="sm"
              border="1px solid"
              borderColor="gray.200"
              p={3}
            >
              <Flex justify="space-between" align="flex-start" gap={3} flexWrap="wrap">
                <Box flex="1" minW="240px">
                  <Text fontWeight="700">{doc.filename}</Text>
                  <Text fontSize="xs" color="gray.700" mt={1}>
                    Status: {doc.is_indexed ? "Indexed" : "Not indexed"}
                  </Text>
                  <Text fontSize="xs" color="gray.700">
                    Chunks: {doc.chunk_count ?? 0}
                  </Text>
                  <Text fontSize="xs" color="gray.700">
                    Last indexed: {doc.last_indexed_at || "—"}
                  </Text>
                </Box>
                <Flex gap={2} flexWrap="wrap">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReindexOne(doc.filename)}
                    isDisabled={busy}
                  >
                    {doc.is_indexed ? "Re-index" : "Index"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onDeleteIndex(doc.filename)}
                    isDisabled={busy || !doc.is_indexed}
                  >
                    Delete index
                  </Button>
                </Flex>
              </Flex>
            </Box>
          ))}
        </Stack>
      </Box>
      {orphanedIndexes.length > 0 && (
        <Box border="1px solid" borderColor="black" p={4} bg="gray.50">
          <Text fontWeight="800" mb={2} fontSize="sm">
            Orphaned indexes
          </Text>
          <Text fontSize="sm" color="gray.700" mb={3}>
            These vectors exist in the store, but their PDF file is no longer in
            `data/pdfs`.
          </Text>
          <Stack spacing={2}>
            {orphanedIndexes.map((item) => (
              <Box key={item.filename} border="1px solid" borderColor="gray.300" p={3} bg="white">
                <Text fontSize="sm" fontWeight="700">
                  {item.filename}
                </Text>
                <Text fontSize="xs" color="gray.700">
                  Chunks: {item.chunk_count ?? 0}
                </Text>
                <Text fontSize="xs" color="gray.700">
                  Last indexed: {item.last_indexed_at || "—"}
                </Text>
              </Box>
            ))}
          </Stack>
        </Box>
      )}
    </Stack>
  );
}
