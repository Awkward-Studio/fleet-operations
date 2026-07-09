import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const imageFile = formData.get("image") as File | null;
    
    if (!imageFile) {
      return NextResponse.json(
        { error: "No image file provided." },
        { status: 400 }
      );
    }

    const apiToken = process.env.PLATE_RECOGNIZER_TOKEN;

    // Fallback: If no API token is configured, simulate OCR for Indian plates to allow testing.
    if (!apiToken) {
      // Simulate network latency of 1.5 seconds
      await new Promise((resolve) => setTimeout(resolve, 1500));
      
      // Return a simulated Indian license plate based on random generation or dummy file name match
      const states = ["DL", "MH", "KA", "HR", "UP", "KA", "GJ", "TS", "AP", "WB"];
      const randomState = states[Math.floor(Math.random() * states.length)];
      const randomDistrict = Math.floor(Math.random() * 99).toString().padStart(2, "0");
      const randomSeries = String.fromCharCode(
        65 + Math.floor(Math.random() * 26),
        65 + Math.floor(Math.random() * 26)
      );
      const randomDigits = Math.floor(Math.random() * 9999).toString().padStart(4, "0");
      const simulatedPlate = `${randomState}${randomDistrict}${randomSeries}${randomDigits}`;

      return NextResponse.json({
        plate: simulatedPlate,
        confidence: 0.95,
        region: "in",
        simulated: true,
        message: "Demo/simulation plate returned because PLATE_RECOGNIZER_TOKEN is not set."
      });
    }

    // Call Plate Recognizer API
    const plateRecFormData = new FormData();
    plateRecFormData.append("upload", imageFile);
    plateRecFormData.append("regions", "in"); // Focus on Indian license plates

    const response = await fetch("https://api.platerecognizer.com/v1/plate-reader/", {
      method: "POST",
      headers: {
        Authorization: `Token ${apiToken}`,
      },
      body: plateRecFormData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `Plate Recognizer API error: ${errorText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    const results = data.results || [];
    
    if (results.length === 0) {
      return NextResponse.json(
        { error: "No license plate recognized in the uploaded image." },
        { status: 422 }
      );
    }

    const bestMatch = results[0];
    const rawPlate = bestMatch.plate || "";
    
    // Format plate string (e.g., uppercase and clean spaces)
    const formattedPlate = rawPlate.toUpperCase().replace(/\s+/g, "");

    return NextResponse.json({
      plate: formattedPlate,
      confidence: bestMatch.confidence,
      region: bestMatch.region?.code || "in",
      simulated: false,
    });
  } catch (error) {
    console.error("ALPR processing error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal Server Error" },
      { status: 500 }
    );
  }
}
