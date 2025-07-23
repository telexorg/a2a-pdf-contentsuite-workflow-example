import httpx
import asyncio
import base64


async def download_file_content(uri: str) -> str:
    """
    Downloads file content from URI and returns it as a base64-encoded string.
    We allow for files that take a minute to download for now
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(uri)
            response.raise_for_status()
            print(f"Successfully downloaded remote file: {response.text[:100]}", uri)
            return base64.b64encode(response.content).decode()
    except Exception as e:
        raise RuntimeError(f"Failed to download file from {uri}: {str(e)}")



if __name__ == "__main__":
    uri = "https://media.telex.im/telexstagingbucket/public/file-uploads/ee0c44f5dbe766b98034a95b956c9ff03bd2353da5b08eaf2cf15ef13558cbab.pdf"
    asyncio.run(download_file_content(uri))
