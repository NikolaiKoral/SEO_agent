import asyncio
import json
import os
import logging

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO, # Set to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ensure the script can find the seo_agent_hub module
# This might need adjustment depending on how the project is structured
# or if it's installed as a package.
import sys
# Assuming the script is run from the SEO_agent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    from seo_agent_hub.orchestrator import SEOOrchestrator
except ImportError as e:
    print(f"Error importing SEOOrchestrator: {e}")
    print("Please ensure you are running this script from the SEO_agent directory",
          "or that the seo_agent_hub package is installed correctly.")
    sys.exit(1)

async def main():
    """
    Initializes and runs the SEOOrchestrator for a sample product.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting orchestrator test...")

    # --- Sample Product Data ---
    # Replace with realistic data for testing
    sample_product_data = {
        "ean": "1234567890123", # Example EAN
        "title": "Example Cloud Accounting Software",
        "brand": "ExampleSoft",
        "category": "Software > Business > Accounting",
        "product_url": "https://example.com/products/cloud-accounting", # Example URL
        "merchant_center_id": "online:en:DK:1234567890123" # Example MC ID format
        # Add any other relevant initial product fields
    }
    logger.info(f"Using sample product data: {sample_product_data}")

    # --- Initialize Orchestrator ---
    # Assumes necessary environment variables (API keys, IDs) are set
    # or a config file is used (though not explicitly passed here)
    try:
        # Pass config path if needed, e.g., config_path='path/to/your/config.json'
        orchestrator = SEOOrchestrator()
        logger.info("SEOOrchestrator initialized.")
    except ImportError as e:
         logger.error(f"Failed to initialize SEOOrchestrator: {e}. Make sure google-a2a is installed.")
         return
    except Exception as e:
        logger.exception("An unexpected error occurred during orchestrator initialization.")
        return

    # --- Run Orchestrator ---
    try:
        logger.info(f"Calling orchestrator.process_product for EAN: {sample_product_data.get('ean')}...")
        final_context = await orchestrator.process_product(sample_product_data)
        logger.info("Orchestrator process_product finished.")

        # --- Print Results ---
        print("\n" + "="*20 + " Final Context " + "="*20)
        print(json.dumps(final_context, indent=2))
        print("="*55)

        # --- Optional: Inspect Shared Memory ---
        # You might want to inspect the final state of shared memory for debugging
        # final_memory = orchestrator.memory.get_all()
        # print("\n" + "="*20 + " Final Shared Memory " + "="*20)
        # print(json.dumps(final_memory, indent=2, default=str)) # Use default=str for non-serializable items
        # print("="*61)


    except Exception as e:
        logger.exception("An error occurred during orchestrator processing.")

if __name__ == "__main__":
    # Ensure environment variables are loaded if using a .env file
    # from dotenv import load_dotenv
    # load_dotenv() # Uncomment if you use a .env file in the root

    asyncio.run(main())
