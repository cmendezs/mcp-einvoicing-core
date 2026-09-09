import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLlmsTxt from "starlight-llms-txt";

export default defineConfig({
  site: "https://cmendezs.github.io",
  base: "/mcp-einvoicing-core/",
  integrations: [
    starlight({
      title: "mcp-einvoicing-core",
      description: "Base package for electronic invoicing MCP servers: compliance logic and signing keys stay yours, never a vendor's",
      customCss: ["./src/styles/docs-theme.css"],
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/cmendezs/mcp-einvoicing-core" },
      ],
      locales: {
        root: { label: "English", lang: "en" },
        fr: { label: "Français", lang: "fr" },
        de: { label: "Deutsch", lang: "de" },
        it: { label: "Italiano", lang: "it" },
        es: { label: "Español", lang: "es" },
        "pt-br": { label: "Português (Brasil)", lang: "pt-BR" },
        ar: { label: "العربية", lang: "ar", dir: "rtl" },
      },
      sidebar: [
        { label: "Overview", link: "/" },
        { label: "Tools", link: "/tools/" },
        { label: "Changelog", link: "/changelog/" },
        { label: "Contributing", link: "/contributing/" },
        { label: "Security", link: "/security/" },
        { label: "Code of Conduct", link: "/code-of-conduct/" },
      ],
      plugins: [
        starlightLlmsTxt({
          projectName: "mcp-einvoicing-core",
          description: "Base package for electronic invoicing MCP servers: compliance logic and signing keys stay yours, never a vendor's",
          customSets: [
            {
              label: "Key links",
              description: "PyPI and MCP registry entries",
              links: ["https://pypi.org/project/mcp-einvoicing-core/", "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.cmendezs/mcp-einvoicing-core"],
            },
          ],
        }),
      ],
    }),
  ],
});
