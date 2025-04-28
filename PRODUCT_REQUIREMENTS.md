# Product Requirements

This should be a publicly available and free (rate-limited) service that can bring chatGPT into your notion comment discussions.

## Product/Vision
Notion thinkers today must context switch to external AI apps, breaking flow and introducing friction.
- Notion is a powerful platform that I use for thinking, planning, writing and organizing my thoughts. AI models like chatGPT and Claude are too. The vision is to bring both of these things into the same environment.
- Success looks like having the benefits of a thinking and writing assistant directly accessible in Notion.

## User Persona
- Individual knowledge workers who use Notion as a place to think, write and organize.

### Success looks like
- Users can prompt an AI directly within the Notion app without breaking their flow, cluttering their space or distracting them.
- Users can set this up and get started prompting within a few minutes with minimal setup and friction.
- Users can direct prompts at the AI with a command ("/ai" or "@ai") and start getting a response streamed to the discussion thread.
- Users use this service regularly and don't need to context switch for text-based questions and prompts.

## KPIs
- MAU - Monthly active users
- User retention - I'm aiming for long term membership by providing this for free
- Average cost per request
- Setup completion rate: how many people sign in with Notion but never send their first prompt
- Setup time and steps: how long does it take in (seconds) and (clicks/keystrokes) to issue their first prompt
- Requests per user per month

## Features
### v0
- [ ] Secure token storage (encryption at rest)

### v1
- [x] Publicly hosted landing page with simple and clean, minimalist UI
- [x] Sign in with Notion
- [x] Rate limiting usage based on tier
- [x] Add the integration to any page to begin chatting
- [ ] The content in the parent block of a comment is infused into the conversation.
- [ ] It can reply quickly with indications of it's thinking process and tool calls.
- [ ] Trigger word for the AI ("/ai")

### v2
- [ ] Free tier and a paid, "unlimited" tier
- [ ] Rich text support
- [ ] Image and file support

## Integrations
- Notion API + Public Integration
- Azure App Service hosting
- LLM Provider + Fallback for outages
