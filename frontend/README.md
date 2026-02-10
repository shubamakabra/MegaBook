# MegaBook Frontend

Tauri + React + TypeScript frontend for MegaBook.

## Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run Tauri dev
npm run tauri dev
```

## Project Structure

```
src/
  components/    # React components
  pages/         # Page components
  services/      # API services
  hooks/         # Custom React hooks
  types/         # TypeScript types
  App.tsx        # Main app component
  main.tsx       # Entry point
```

## Features (Planned)

- File tree explorer for repository navigation
- Markdown editor for notes
- Admin panel for pipeline control
- Session notes input (Notepad++ style)
- Diff viewer for proposed changes
- Chat interface for RAG queries
- Cost monitoring dashboard

## Architecture

The frontend communicates with the FastAPI backend via HTTP API.
All filesystem operations go through the backend - the frontend never accesses files directly.