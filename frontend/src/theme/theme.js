import { extendTheme } from "@chakra-ui/react";

const border = "1px solid";
const borderColor = "black";

export const theme = extendTheme({
  config: {
    initialColorMode: "light",
    useSystemColorMode: false,
  },
  styles: {
    global: {
      body: {
        bg: "white",
        color: "black",
      },
    },
  },
  components: {
    Button: {
      baseStyle: {
        borderRadius: "none",
        border,
        borderColor,
        fontWeight: "600",
      },
      variants: {
        solid: {
          bg: "black",
          color: "white",
          _hover: { bg: "gray.800" },
        },
        outline: {
          bg: "white",
          color: "black",
          border,
          borderColor,
          _hover: { bg: "gray.50" },
        },
      },
      defaultProps: {
        variant: "outline",
      },
    },
    Input: {
      variants: {
        outline: {
          field: {
            borderRadius: "none",
            border,
            borderColor,
            _focus: {
              borderColor: "black",
              boxShadow: "none",
            },
          },
        },
      },
      defaultProps: {
        variant: "outline",
      },
    },
    Textarea: {
      variants: {
        outline: {
          borderRadius: "none",
          border,
          borderColor,
          _focus: {
            borderColor: "black",
            boxShadow: "none",
          },
        },
      },
      defaultProps: {
        variant: "outline",
      },
    },
    NumberInput: {
      variants: {
        outline: {
          field: {
            borderRadius: "none",
            border,
            borderColor,
          },
        },
      },
    },
    Card: {
      baseStyle: {
        container: {
          borderRadius: "none",
          border,
          borderColor,
          bg: "white",
          boxShadow: "none",
        },
      },
    },
    Tabs: {
      variants: {
        line: {
          tab: {
            borderRadius: "none",
            fontWeight: "600",
            _selected: {
              color: "black",
              borderColor: "black",
            },
          },
        },
      },
    },
  },
});
