import { Route, Routes, NavLink } from "react-router-dom";
import {
  Box,
  Container,
  Flex,
  Heading,
  HStack,
  Text,
} from "@chakra-ui/react";
import ChatPage from "./pages/ChatPage.jsx";
import DocumentsPage from "./pages/DocumentsPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

const navSx = {
  px: 3,
  py: 2,
  border: "1px solid",
  borderColor: "black",
  fontWeight: "700",
  fontSize: "sm",
  _hover: { bg: "gray.50" },
};

function NavItem({ to, children }) {
  return (
    <NavLink to={to} end={to === "/"}>
      {({ isActive }) => (
        <Box
          as="span"
          display="inline-block"
          {...navSx}
          bg={isActive ? "black" : "white"}
          color={isActive ? "white" : "black"}
        >
          {children}
        </Box>
      )}
    </NavLink>
  );
}

export default function App() {
  return (
    <Box h="100dvh" maxH="100dvh" bg="white" display="flex" flexDirection="column" overflow="hidden">
      <Box borderBottom="1px solid" borderColor="black" py={6}>
        <Container maxW="container.lg">
          <Flex justify="space-between" align="flex-start" flexWrap="wrap" gap={4}>
            <Box>
              <Heading size="lg" fontWeight="900" letterSpacing="-0.04em">
                RAG580
              </Heading>
            </Box>
            <HStack spacing={2} flexWrap="wrap">
              <NavItem to="/">Chat</NavItem>
              <NavItem to="/documents">Documents</NavItem>
              <NavItem to="/settings">Settings</NavItem>
            </HStack>
          </Flex>
        </Container>
      </Box>
      <Container maxW="container.lg" py={6} flex="1" minH="0" display="flex" overflow="hidden">
        <Box
          flex="1"
          minH="0"
          overflowY="auto"
          overflowX="hidden"
          sx={{
            scrollbarWidth: "none",
            msOverflowStyle: "none",
            "&::-webkit-scrollbar": {
              display: "none",
            },
          }}
        >
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Box>
      </Container>
      <Box borderTop="1px solid" borderColor="black" py={4}>
        <Container maxW="container.lg">
          <Text fontSize="xs" color="gray.600">
            RAG580
          </Text>
        </Container>
      </Box>
    </Box>
  );
}
