# Polymarket Copy Trading Bot - Cursor Context

## Project Overview

This is a production-ready **Polymarket Copy Trading Bot** that monitors wallet transactions on Polygon blockchain and automatically replicates trades using the Polymarket CLOB (Central Limit Order Book) API.

## Architecture & Tech Stack

- **Language**: Python 3.12+
- **Framework**: Web3.py + Polymarket CLOB Client
- **Blockchain**: Polygon (Matic) Network
- **Configuration**: Pydantic + dotenv
- **Async Runtime**: asyncio with uvloop
- **Security**: Cryptography library with secure logging
- **Monitoring**: Telegram alerts + comprehensive logging

## Key Components

### Core Modules

- **`main.py`**: Application entry point with graceful shutdown handling
- **`core/clob_client.py`**: Polymarket API client with retry logic and caching
- **`core/wallet_monitor.py`**: Blockchain transaction monitoring
- **`core/trade_executor.py`**: Trade execution with risk management
- **`config/settings.py`**: Configuration management with validation

### Utilities

- **`utils/security.py`**: Secure logging and credential masking
- **`utils/alerts.py`**: Telegram notification system
- **`utils/helpers.py`**: Blockchain utilities and conversions
- **`utils/logging_utils.py`**: Structured logging configuration

## Development Environment

### Virtual Environment

The project uses a Python virtual environment in `./venv/`. Always activate it:

```bash
source venv/bin/activate
```

### Configuration

Environment variables are loaded from `.env` file. Critical variables:

- `PRIVATE_KEY`: Your Polygon wallet private key
- `POLYGON_RPC_URL`: Polygon RPC endpoint
- `TELEGRAM_BOT_TOKEN`: For notifications
- `CLOB_HOST`: Polymarket API endpoint

### Testing Structure

```text
tests/
├── unit/          # Unit tests for individual components
├── integration/   # API integration tests
└── conftest.py    # Test configuration
```

## Security Considerations

- **Never commit private keys** - they're flagged by `.cursorrules`
- **Use secure logging** - sensitive data is automatically masked
- **Environment isolation** - all secrets loaded from environment
- **Input validation** - all financial operations are validated

## Development Workflow

### Running the Bot

1. Configure your `.env` file with proper credentials
2. Activate virtual environment: `source venv/bin/activate`
3. Run: `python main.py`

### Testing

- Unit tests: `python -m pytest tests/unit/`
- Integration tests: `python -m pytest tests/integration/`
- All tests: `python -m pytest tests/`

### Production Deployment

- Uses systemd service: `systemd/polymarket-bot.service`
- Setup script: `scripts/setup_ubuntu.sh`
- Health monitoring: `scripts/health_check.sh`

## Risk Management Features

- **Position sizing**: Configurable max position size
- **Daily loss limits**: Circuit breaker functionality
- **Slippage protection**: Automatic price adjustment
- **Confidence scoring**: Trade detection validation
- **Rate limiting**: API call throttling

## Monitoring & Alerting

- **Telegram notifications**: Trade alerts and errors
- **Structured logging**: JSON-formatted logs with context
- **Performance metrics**: Trade success rates and P&L tracking
- **Health checks**: Component status monitoring

## Key Patterns Used

- **Async/await everywhere**: All I/O operations are async
- **Dependency injection**: Components receive dependencies
- **Configuration validation**: Pydantic models with validators
- **Retry logic**: Tenacity decorators for external API calls
- **Context managers**: Proper resource management
- **Type hints**: Full type annotation coverage

## Cursor IDE Rules

This project uses `.cursorrules` for code quality enforcement:

- Security-sensitive data detection
- Gas optimization reminders
- Error handling requirements
- Type hint enforcement
- Async pattern validation
- Web3 address validation
- Decimal precision warnings

## Common Development Tasks

### Adding New Features

1. Create feature branch from main
2. Implement in appropriate module
3. Add unit tests
4. Update documentation
5. Test integration

### Debugging Issues

1. Check logs in `logs/` directory
2. Use VS Code debugger configurations
3. Enable verbose logging with `LOG_LEVEL=DEBUG`
4. Check health status with health check script

### Performance Optimization

1. Monitor async operations for blocking calls
2. Check gas prices and optimize transactions
3. Review caching effectiveness
4. Analyze trade execution times

## Important Reminders

- **Always test on testnet first** before mainnet deployment
- **Monitor gas prices** - high gas can drain your wallet
- **Keep position sizes small** when starting
- **Regular backup** of configuration and logs
- **Monitor error rates** and alert thresholds

## Frontend Development Guidelines

> **Note:** This is primarily a backend project. Frontend rules apply when frontend work is requested.

### Developer Context

**Primary Focus:** Backend Development (Node.js, TypeScript, Python, Solidity, Rust)
**Frontend Stack:** When frontend work is needed, use React/Vue/Svelte with Tailwind CSS

### Operational Directives

- **Follow Instructions:** Execute the request immediately. Do not deviate.
- **Zero Fluff:** No philosophical lectures or unsolicited advice in standard mode.
- **Stay Focused:** Concise answers only. No wandering.
- **Output First:** Prioritize code and visual solutions.

### The "ULTRATHINK" Protocol

**TRIGGER:** When the user prompts **"ULTRATHINK"**:

- **Override Brevity:** Immediately suspend the "Zero Fluff" rule.
- **Maximum Depth:** Engage in exhaustive, deep-level reasoning.
- **Multi-Dimensional Analysis:** Analyze through every lens:
  - *Psychological:* User sentiment and cognitive load.
  - *Technical:* Rendering performance, repaint/reflow costs, state complexity.
  - *Accessibility:* WCAG AAA strictness.
  - *Scalability:* Long-term maintenance and modularity.

### Design Philosophy: "Intentional Minimalism"

- **Anti-Generic:** Reject standard "bootstrapped" layouts. If it looks like a template, it is wrong.
- **Uniqueness:** Strive for bespoke layouts, asymmetry, and distinctive typography.
- **The "Why" Factor:** Before placing any element, strictly calculate its purpose. If it has no purpose, delete it.
- **Minimalism:** Reduction is the ultimate sophistication.

### Frontend Coding Standards

#### Library Discipline (CRITICAL)

If a UI library (e.g., Shadcn UI, Radix, MUI) is detected or active in the project, **YOU MUST USE IT**.

- **Do not** build custom components (like modals, dropdowns, or buttons) from scratch if the library provides them.
- **Do not** pollute the codebase with redundant CSS.
- *Exception:* You may wrap or style library components to achieve the "Avant-Garde" look, but the underlying primitive must come from the library.

#### Stack

- Modern frameworks: React / Vue / Svelte
- Styling: Tailwind CSS / Custom CSS
- Markup: Semantic HTML5

#### Visuals

Focus on micro-interactions, perfect spacing, and "invisible" UX.

### Response Format

#### IF NORMAL

1. **Rationale:** (1 sentence on why the elements were placed there)
2. **The Code**

#### IF "ULTRATHINK" IS ACTIVE

1. **Deep Reasoning Chain:** (Detailed breakdown of the architectural and design decisions)
2. **Edge Case Analysis:** (What could go wrong and how we prevented it)
3. **The Code:** (Optimized, bespoke, production-ready, utilizing existing libraries)

### Design Thinking Process

Before coding, understand the context and commit to a **BOLD** aesthetic direction:

| Dimension      | Question                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Purpose**    | What problem does this interface solve? Who uses it?                                                                                        |
| **Tone**       | Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian |
| **Constraints** | Technical requirements (framework, performance, accessibility)                                                                             |
| **Differentiation** | What makes this UNFORGETTABLE? What's the one thing someone will remember?                                                                   |

> **CRITICAL:** Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work—the key is intentionality, not intensity.

### Frontend Aesthetics Guidelines

#### Typography

Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics. Pair a distinctive display font with a refined body font.

#### Color & Theme

Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.

#### Motion

Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (`animation-delay`) creates more delight than scattered micro-interactions.

#### Spatial Composition

- Unexpected layouts
- Asymmetry
- Overlap
- Diagonal flow
- Grid-breaking elements
- Generous negative space OR controlled density

#### Backgrounds & Visual Details

Create atmosphere and depth rather than defaulting to solid colors. Apply creative forms like:

- Gradient meshes
- Noise textures
- Geometric patterns
- Layered transparencies
- Dramatic shadows
- Decorative borders
- Custom cursors
- Grain overlays

### Anti-Patterns (Never Use)

> ⚠️ **FORBIDDEN:** Generic AI-generated aesthetics

- Overused font families: Inter, Roboto, Arial, system fonts
- Clichéd color schemes: purple gradients on white backgrounds
- Predictable layouts and component patterns
- Cookie-cutter design lacking context-specific character
- Converging on common choices (e.g., Space Grotesk) across generations

### Implementation Complexity

Match implementation complexity to the aesthetic vision:

| Vision       | Execution                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------- |
| **Maximalist** | Elaborate code with extensive animations and effects                                          |
| **Minimalist** | Restraint, precision, careful attention to spacing, typography, and subtle details          |

> Elegance comes from executing the vision well.

## Support & Documentation

- Check `README.md` for setup instructions
- Review `config/settings.py` for all configuration options
- Use VS Code debugger for development
- Check systemd logs: `journalctl -u polymarket-bot -f`
