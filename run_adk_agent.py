from brand_search_optimization.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.adk.sessions.session import Session
from google.genai import types as genai_types

def run_agent_sync():
    print("Initializing InMemoryRunner...")
    # Use InMemoryRunner for local execution
    runner = InMemoryRunner(agent=root_agent, app_name="brand-optimizer-local")

    user_id = "local-user"
    session_id = "local-session"
    brand_name = "Royal Copenhagen"

    # Create a new session using the session service
    session = runner.session_service.create_session(
        app_name="brand-optimizer-local",
        user_id=user_id,
        session_id=session_id
    )

    # Create the input message using google.genai types
    input_message = genai_types.Content(
        parts=[genai_types.Part(text=brand_name)],
        role="user"
    )

    print(f"Running agent for brand: {brand_name}...")
    try:
        # Use the synchronous run method which handles the async loop
        for event in runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=input_message,
        ):
            if event.content and event.content.parts:
                output = ''.join(p.text for p in event.content.parts if p.text)
                if output:
                    print(f"--- Agent Event ({event.author}) ---")
                    print(output)
                    print("-" * (len(f"Agent Event ({event.author})") + 6))

            # You can uncomment this to see the full event structure
            # print(f"Raw Event: {event.model_dump_json(indent=2)}")

    except Exception as e:
        print(f"An error occurred during agent run: {e}")
    finally:
        print("Agent run finished.")
        # Clean up the session
        runner.close_session(session)

if __name__ == "__main__":
    run_agent_sync()
