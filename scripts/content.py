"""
Single source of truth for everything personal in the profile.

Card layout lives in generate_cards.py; wording lives here. Anything that is a
fact about Al Shahriar Sowan (links, products, roles, education) is kept in this
file so it can be reviewed and edited without touching the SVG engine.

Only facts supported by the resume and the brief belong here. No star counts,
download numbers, user numbers, dates that were not provided, or invented
features.
"""

IDENTITY = {
    "name": "Al Shahriar Sowan",
    "name_lines": ("Al Shahriar", "Sowan"),
    "title": "Jr. Software & AI Integration Developer",
    "founded": "Founder of EAGOX Studio",
    "studio": "EAGOX Studio",
    "tagline": "Building Software. Integrating AI. Shipping Products.",
    "location": "Gazipur, Bangladesh",
    "location_short": "DHAKA, BD",
    "github": "https://github.com/Alshahriar-07",
    "github_handle": "Alshahriar-07",
    "portfolio": "https://alshahriarsayon.vercel.app/",
    "portfolio_label": "alshahriarsayon.vercel.app",
    "linkedin": "https://www.linkedin.com/in/alshahriarsowan",
    "linkedin_label": "in/alshahriarsowan",
    "email": "alshahriarsayon425@gmail.com",
    "profile_repo": "Alshahriar-07/Alshahriar-07",
}

# The three linked tiles under the hero. 32.5% each in the README.
TILES = [
    {
        "slug": "portfolio",
        "index": "01",
        "label": "Portfolio",
        "url": IDENTITY["portfolio"],
        "display": IDENTITY["portfolio_label"],
        "blurb": "Selected work and products.",
    },
    {
        "slug": "github",
        "index": "02",
        "label": "GitHub",
        "url": IDENTITY["github"],
        "display": "github.com/Alshahriar-07",
        "blurb": "Source, commits and experiments.",
    },
    {
        "slug": "linkedin",
        "index": "03",
        "label": "LinkedIn",
        "url": IDENTITY["linkedin"],
        "display": IDENTITY["linkedin_label"],
        "blurb": "Experience, education and contact.",
    },
]

# Headline numbers used in the hero and about card. All are countable facts.
FACTS = [
    ("06", "PRODUCTS SHIPPED"),
    ("04", "PLATFORMS"),
    ("02", "CLIENT PROJECTS"),
]

ABOUT_TERMINAL = [
    ("$", "whoami"),
    (" ", "Al Shahriar Sowan - software & AI integration developer."),
    ("$", "cat focus.txt"),
    (" ", "I plan, build and ship software on my own: web, desktop,"),
    (" ", "Android and command-line products. Six shipped so far, all"),
    (" ", "built and deployed under EAGOX Studio."),
    ("$", "cat ai.txt"),
    (" ", "Most of my work is wiring AI into software people can use:"),
    (" ", "OpenAI-compatible APIs, OpenRouter, Ollama, tool calling"),
    (" ", "and local models inside real products, not demos."),
]

ABOUT_RAIL = [
    ("STUDIO", "EAGOX Studio"),
    ("BASE", "Gazipur, Bangladesh"),
    ("ROLE", "Founder & independent developer"),
    ("STUDYING", "Diploma in CSE, 3rd semester"),
    ("FOCUS", "AI integration · product engineering"),
]

# Six independently built and deployed products. Descriptions are the resume's,
# lightly edited for length. Live URLs are verified; only seedcode-cli has a
# repository link that was provided.
PROJECTS = [
    {
        "slug": "seed-code-chat",
        "index": "01",
        "name": "Seed Code Chat",
        "desc": "A web and Android AI assistant that works with multiple AI providers.",
        "category": "WEB + ANDROID",
        "tags": "MULTI-PROVIDER AI",
        "live": "https://seedcode-chat.vercel.app",
        "repo": "",
    },
    {
        "slug": "seed-code-mail",
        "index": "02",
        "name": "Seed Code Mail",
        "desc": "A Gmail API email workspace with campaigns, sending history, Supabase Auth and row-level security.",
        "category": "WEB",
        "tags": "GMAIL API · SUPABASE AUTH · RLS",
        "live": "https://mrseedmail.vercel.app",
        "repo": "",
    },
    {
        "slug": "mr-mesoff",
        "index": "03",
        "name": "MR MESOFF",
        "desc": "One desktop inbox for WhatsApp Business, Instagram Professional and Messenger, with AI-assisted replies.",
        "category": "DESKTOP",
        "tags": "WHATSAPP · INSTAGRAM · MESSENGER",
        "live": "https://mrmesoff.vercel.app",
        "repo": "",
    },
    {
        "slug": "seedcode-cli",
        "index": "04",
        "name": "SeedCode CLI v10.2.1",
        "desc": "An AI command-line development assistant with local and cloud models, plus tool calling.",
        "category": "CLI",
        "tags": "LOCAL + CLOUD MODELS · TOOL CALLING",
        "live": "https://seedcode-cli.vercel.app",
        "repo": "https://github.com/Alshahriar-07/seedcode-cli",
    },
    {
        "slug": "intllm",
        "index": "05",
        "name": "IntLLM Local AI",
        "desc": "A local AI environment with memory, tools and live information.",
        "category": "LOCAL AI",
        "tags": "MEMORY · TOOLS · LIVE INFO",
        "live": "https://intllm.vercel.app",
        "repo": "",
    },
    {
        "slug": "dorkey",
        "index": "06",
        "name": "Dorkey",
        "desc": "A typing speed test with WPM, CPM, accuracy, errors, timed sessions and ranking.",
        "category": "WEB TOOL",
        "tags": "WPM · CPM · ACCURACY · RANKING",
        "live": "https://dorkey.vercel.app",
        "repo": "",
    },
]

SKILLS = [
    ("01", "Programming & Backend", ["Python", "JavaScript", "HTML", "CSS", "FastAPI"]),
    ("02", "API & Integration", ["REST APIs", "Gmail API", "OpenAI-compatible APIs", "API authentication", "AI tool calling"]),
    ("03", "Database & Auth", ["Supabase", "Supabase Auth", "Row Level Security", "Database management"]),
    ("04", "AI & LLM", ["OpenRouter", "Ollama", "Multi-provider LLM integration", "Local AI model integration"]),
    ("05", "Tools & Deployment", ["Git", "GitHub", "Vercel", "Cloudflare Workers", "Cloudflare R2", "VS Code", "Linux"]),
]

EXPERIENCE = [
    {
        "role": "Founder & Independent Developer",
        "org": "EAGOX Studio",
        "meta": "PRESENT",
        "place": "Independent software studio",
        "bullets": [
            "Planned, developed and deployed six software products on my own.",
            "Shipped across web, desktop, Android and command-line platforms.",
            "Handled AI integration, APIs, authentication, databases and deployment.",
        ],
    },
    {
        "role": "Freelance Developer",
        "org": "Direct client work",
        "meta": "DELIVERED",
        "place": "2 projects delivered",
        "bullets": [
            "Photographer portfolio with a booking and enquiry form (HTML, CSS, JavaScript).",
            "English-learning app with real-time AI voice conversation, built with Python, FastAPI, JavaScript and an OpenAI-compatible API.",
        ],
    },
    {
        "role": "Junior System Deployment Engineer",
        "org": "TriTech Computers and Engineering",
        "meta": "MAY 2026 - OCT 2026",
        "place": "Client: City Bank PLC",
        "bullets": [
            "Supported deployment across six branches.",
            "Installed operating systems and assisted with network configuration and troubleshooting.",
            "Resolved hardware, software and system-related issues.",
        ],
    },
]

EDUCATION = [
    {
        "degree": "Diploma in Engineering",
        "field": "Computer Science & Technology",
        "school": "Dhaka Polytechnic Institute, Dhaka",
        "meta": "SEP 2025 - PRESENT",
        "note": "3rd semester",
    },
    {
        "degree": "Secondary School Certificate",
        "field": "SSC · Mymensingh Board",
        "school": "Hashil Higher Secondary School",
        "meta": "2025",
        "note": "GPA 4.72 / 5.00",
    },
]

SECTION_TITLES = {
    "work": ("04", "SELECTED WORK", "Six products, ", "built and shipped"),
}
