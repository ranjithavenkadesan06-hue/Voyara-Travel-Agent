
import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [screen, setScreen] = useState("landing");
  const [showAuth, setShowAuth] = useState(false);
  const [user, setUser] = useState(null);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [travelData, setTravelData] = useState(null);
  const [error, setError] = useState("");

  const [selectedFlight, setSelectedFlight] = useState(null);
  const [selectedHotel, setSelectedHotel] = useState(null);

  const [showEmail, setShowEmail] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const [mobileMenu, setMobileMenu] = useState(false);

  // ============================================================
  // RESTORE JWT LOGIN SESSION
  // ============================================================

  useEffect(() => {
    const restoreSession = async () => {
      const token = localStorage.getItem("voyara_token");

      if (!token) {
        return;
      }

      try {
        const response = await fetch(`${API_URL}/auth/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error("Session expired");
        }

        const userData = await response.json();

        localStorage.setItem(
          "voyara_user",
          JSON.stringify(userData)
        );

        setUser(userData);
        setScreen("dashboard");
      } catch (err) {
        console.error("Session restore failed:", err);

        localStorage.removeItem("voyara_token");
        localStorage.removeItem("voyara_user");

        setUser(null);
        setScreen("landing");
      }
    };

    restoreSession();
  }, []);

  // ============================================================
  // AUTHENTICATION
  // ============================================================

  const handleLogin = async (email, password) => {
    const cleanEmail = email.trim();

    if (!cleanEmail || !password) {
      throw new Error("Email and password are required.");
    }

    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: cleanEmail,
        password: password,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Invalid email or password."
      );
    }

    const token = data.access_token;

    localStorage.setItem("voyara_token", token);

    const userResponse = await fetch(`${API_URL}/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const userData = await userResponse.json();

    if (!userResponse.ok) {
      localStorage.removeItem("voyara_token");

      throw new Error(
        userData.detail || "Unable to load user."
      );
    }

    localStorage.setItem(
      "voyara_user",
      JSON.stringify(userData)
    );

    setUser(userData);
    setShowAuth(false);
    setScreen("dashboard");
  };

  const handleRegister = async (
    name,
    email,
    password
  ) => {
    const cleanName = name.trim();
    const cleanEmail = email.trim();

    if (!cleanName || !cleanEmail || !password) {
      throw new Error(
        "Please fill in all the required fields."
      );
    }

    const response = await fetch(
      `${API_URL}/auth/register`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: cleanName,
          email: cleanEmail,
          password: password,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Registration failed."
      );
    }

    await handleLogin(cleanEmail, password);
  };

  const requireAuth = (action) => {
    if (!user) {
      setShowAuth(true);
      return;
    }

    action();
  };

  const handleLogout = () => {
    localStorage.removeItem("voyara_token");
    localStorage.removeItem("voyara_user");

    setUser(null);
    setScreen("landing");

    setSearched(false);
    setQuery("");
    setTravelData(null);
    setSelectedFlight(null);
    setSelectedHotel(null);
    setShowEmail(false);
    setEmailSent(false);
    setError("");
  };

  // ============================================================
  // TRAVEL SEARCH
  // ============================================================

  const handleSearch = async () => {
    if (!query.trim()) return;

    setSearching(true);
    setSearched(false);
    setError("");
    setTravelData(null);
    setSelectedFlight(null);
    setSelectedHotel(null);

    try {
      const response = await fetch(`${API_URL}/travel`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create your journey"
        );
      }

      console.log("Voyara travel response:", data);

      setTravelData(data);
      setSearched(true);
    } catch (err) {
      console.error("Travel error:", err);

      setError(
        err.message ||
          "Something went wrong while creating your journey."
      );
    } finally {
      setSearching(false);
    }
  };

  const useSuggestion = (text) => {
    setQuery(text);
  };

  const openDashboard = () => {
    requireAuth(() => {
      setScreen("dashboard");
    });
  };

  // ============================================================
  // SEND ITINERARY EMAIL
  // ============================================================

  const handleSendEmail = async () => {
    if (!user?.email) {
      alert("Please login first.");
      return;
    }

    if (!travelData?.thread_id) {
      alert(
        "Travel session not found. Please search again."
      );
      return;
    }

    try {
      setSendingEmail(true);

      const response = await fetch(
        `${API_URL}/send-email`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            receiver_email: user.email,
            subject: "Your Voyara Travel Itinerary",
            thread_id: travelData.thread_id,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.message || "Failed to send itinerary"
        );
      }

      console.log(
        "Email successfully accepted by SendGrid:",
        data
      );

      setSendingEmail(false);
      setEmailSent(true);

      setTimeout(() => {
        setEmailSent(false);
        setShowEmail(false);
      }, 2200);
    } catch (err) {
      console.error("Email error:", err);

      setSendingEmail(false);

      alert(
        err.message || "Failed to send itinerary"
      );
    }
  };

  return (
    <div className="voyara-app">

      {/* ======================================================
          NAVBAR
      ====================================================== */}

      <header className="navbar">

        <div
          className="brand"
          onClick={() => {
            if (user) {
              setScreen("dashboard");
            } else {
              setScreen("landing");
            }
          }}
        >
          <div className="brand-mark">V</div>

          <div>
            <div className="brand-name">
              voyara
            </div>

            <div className="brand-tagline">
              AI TRAVEL AGENT
            </div>
          </div>
        </div>

        <nav
          className={`nav-links ${
            mobileMenu ? "mobile-open" : ""
          }`}
        >
          {!user ? (
            <>
              <button
                onClick={() =>
                  setScreen("landing")
                }
              >
                Home
              </button>

              <button
                onClick={() =>
                  requireAuth(() =>
                    setScreen("dashboard")
                  )
                }
              >
                Explore
              </button>

              <button
                onClick={() =>
                  setShowAuth(true)
                }
              >
                Sign in
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() =>
                  setScreen("dashboard")
                }
              >
                Explore
              </button>

              <button
                onClick={() =>
                  requireAuth(() => {
                    if (searched) {
                      window.scrollTo({
                        top: 500,
                        behavior: "smooth",
                      });
                    }
                  })
                }
              >
                My Journey
              </button>

              <button onClick={handleLogout}>
                Sign out
              </button>
            </>
          )}
        </nav>

        <div className="nav-user">

          {user ? (
            <div className="profile-pill">

              <div className="avatar">
                {user.name
                  ?.charAt(0)
                  .toUpperCase()}
              </div>

              <span>
                {user.name?.split(" ")[0]}
              </span>

            </div>
          ) : (
            <button
              className="nav-signin"
              onClick={() =>
                setShowAuth(true)
              }
            >
              Sign in
            </button>
          )}

        </div>

        <button
          className="mobile-menu-button"
          onClick={() =>
            setMobileMenu(!mobileMenu)
          }
        >
          ☰
        </button>

      </header>

      {/* ======================================================
          LANDING
      ====================================================== */}

      {screen === "landing" && (
        <LandingPage
          onExplore={openDashboard}
          onSignIn={() =>
            setShowAuth(true)
          }
        />
      )}

      {/* ======================================================
          DASHBOARD
      ====================================================== */}

      {screen === "dashboard" && user && (
        <Dashboard
          user={user}
          query={query}
          setQuery={setQuery}
          searching={searching}
          searched={searched}
          handleSearch={handleSearch}
          useSuggestion={useSuggestion}
          selectedFlight={selectedFlight}
          setSelectedFlight={setSelectedFlight}
          selectedHotel={selectedHotel}
          setSelectedHotel={setSelectedHotel}
          onEmail={() =>
            setShowEmail(true)
          }
          travelData={travelData}
          error={error}
        />
      )}

      {/* ======================================================
          LOCKED PAGE
      ====================================================== */}

      {!user && screen === "dashboard" && (
        <div className="locked-page">

          <div className="locked-card">

            <div className="lock-icon">
              🔒
            </div>

            <h2>
              Your journey starts here
            </h2>

            <p>
              Create an account or sign in
              to unlock Voyara's AI-powered
              travel planning experience.
            </p>

            <button
              className="primary-button"
              onClick={() =>
                setShowAuth(true)
              }
            >
              Sign in to continue
            </button>

          </div>

        </div>
      )}

      {/* ======================================================
          AUTH MODAL
      ====================================================== */}

      {showAuth && (
        <AuthModal
          onClose={() =>
            setShowAuth(false)
          }
          onLogin={handleLogin}
          onRegister={handleRegister}
        />
      )}

      {/* ======================================================
          EMAIL MODAL
      ====================================================== */}

      {showEmail && (
        <EmailModal
          user={user}
          sendingEmail={sendingEmail}
          emailSent={emailSent}
          onSend={handleSendEmail}
          onClose={() => {
            if (!sendingEmail) {
              setShowEmail(false);
            }
          }}
          selectedFlight={selectedFlight}
          selectedHotel={selectedHotel}
          travelData={travelData}
        />
      )}

    </div>
  );
}

/* ============================================================
   LANDING PAGE
============================================================ */

function LandingPage({
  onExplore,
  onSignIn,
}) {
  return (
    <main className="landing">

      <div className="landing-glow glow-one"></div>
      <div className="landing-glow glow-two"></div>

      <section className="hero-section">

        <div className="hero-copy">

          <div className="eyebrow">
            <span className="pulse-dot"></span>
            YOUR PERSONAL AI TRAVEL AGENT
          </div>

          <h1>
            Travel
            <span> beyond </span>
            ordinary.
          </h1>

          <p className="hero-description">
            Tell Voyara where you want to go.
            We'll turn your thoughts into
            flights, stays and a personalized
            journey — all in one intelligent
            travel experience.
          </p>

          <div className="hero-actions">

            <button
              className="primary-button"
              onClick={onExplore}
            >
              Explore the Journey
              <span>→</span>
            </button>

            <button
              className="secondary-button"
              onClick={onSignIn}
            >
              Sign in
            </button>

          </div>

          <div className="trust-row">

            <div className="trust-item">
              <span>✦</span>
              AI-powered planning
            </div>

            <div className="trust-item">
              <span>✓</span>
              Personalized results
            </div>

            <div className="trust-item">
              <span>✈</span>
              Built for explorers
            </div>

          </div>

        </div>

        <div className="hero-visual">

          <div className="orbit orbit-one"></div>
          <div className="orbit orbit-two"></div>

          <div className="planet-card">

            <div className="planet">
              <div className="planet-land land-one"></div>
              <div className="planet-land land-two"></div>
              <div className="planet-land land-three"></div>
              <div className="planet-cloud cloud-one"></div>
              <div className="planet-cloud cloud-two"></div>
            </div>

          </div>

          <div className="floating-card card-flight">

            <div className="mini-icon">
              ✈
            </div>

            <div>

              <span>
                Next adventure
              </span>

              <strong>
                Chennai → Delhi
              </strong>

            </div>

          </div>

          <div className="floating-card card-ai">

            <div className="ai-spark">
              ✦
            </div>

            <div>

              <span>
                Voyara AI
              </span>

              <strong>
                Journey ready
              </strong>

            </div>

          </div>

        </div>

      </section>

      <section className="landing-bottom">

        <div>
          <span>01</span>

          <strong>
            Tell us where
          </strong>

          <p>
            Describe your dream journey
            naturally.
          </p>
        </div>

        <div>
          <span>02</span>

          <strong>
            AI plans it
          </strong>

          <p>
            Flights, hotels and experiences
            in seconds.
          </p>
        </div>

        <div>
          <span>03</span>

          <strong>
            Travel smarter
          </strong>

          <p>
            Save or send your complete
            itinerary.
          </p>
        </div>

      </section>

    </main>
  );
}

/* ============================================================
   DASHBOARD
============================================================ */

function Dashboard({
  user,
  query,
  setQuery,
  searching,
  searched,
  travelData,
  error,
  handleSearch,
  useSuggestion,
  selectedFlight,
  setSelectedFlight,
  selectedHotel,
  setSelectedHotel,
  onEmail,
}) {
  return (
    <main className="dashboard">

      <section className="dashboard-hero">

        <div className="dashboard-intro">

          <div className="dashboard-greeting">
            Good to see you,{" "}
            {user.name.split(" ")[0]}.
          </div>

          <h1>
            Where will your
            <span> next story </span>
            take you?
          </h1>

          <p>
            Describe your trip naturally.
            Voyara will take care of the
            details.
          </p>

        </div>

        <div className="search-box">

          <div className="search-icon">
            ⌕
          </div>

          <input
            value={query}
            onChange={(e) =>
              setQuery(e.target.value)
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSearch();
              }
            }}
            placeholder='Try “Chennai to Delhi for 4 days”'
          />

          {query && (
            <button
              className="clear-query"
              onClick={() =>
                setQuery("")
              }
            >
              ×
            </button>
          )}

          <button
            className="explore-button"
            onClick={handleSearch}
            disabled={searching}
          >
            {searching ? (
              <span className="button-loader"></span>
            ) : (
              <>
                Explore
                <span>→</span>
              </>
            )}
          </button>

        </div>

        <div className="suggestions">

          <span>
            Try:
          </span>

          <button
            onClick={() =>
              useSuggestion(
                "Chennai to Delhi for 4 days"
              )
            }
          >
            Chennai → Delhi
          </button>

          <button
            onClick={() =>
              useSuggestion(
                "Chennai to Goa for 3 days"
              )
            }
          >
            Chennai → Goa
          </button>

          <button
            onClick={() =>
              useSuggestion(
                "Chennai to Mumbai for 5 days"
              )
            }
          >
            Chennai → Mumbai
          </button>

        </div>

      </section>

      {!searched &&
        !searching &&
        !error && (
          <section className="empty-dashboard">

            <div className="empty-orb">
              ✦
            </div>

            <h2>
              Your next adventure is waiting.
            </h2>

            <p>
              Start with a destination,
              a dream, or simply tell Voyara
              what kind of trip you want.
            </p>

            <div className="example-query">
              “A relaxing 4-day trip to Goa
              with beaches, good food and a
              comfortable hotel.”
            </div>

          </section>
        )}

      {searching && (
        <section className="loading-section">

          <div className="loading-animation">
            <span></span>
            <span></span>
            <span></span>
          </div>

          <h2>
            Building your journey...
          </h2>

          <p>
            Voyara is searching for the best
            possibilities for your trip.
          </p>

          <div className="loading-steps">

            <div>
              ✓ Understanding your request
            </div>

            <div>
              ✓ Finding travel options
            </div>

            <div>
              ○ Creating your itinerary
            </div>

          </div>

        </section>
      )}

      {error && !searching && (
        <section className="error-section">

          <div className="error-card">

            <div className="error-icon">
              !
            </div>

            <div>

              <strong>
                We couldn't build that journey
              </strong>

              <p>
                {error}
              </p>

            </div>

          </div>

        </section>
      )}

      {searched &&
        !searching &&
        travelData && (
          <TravelResults
            travelData={travelData}
            selectedFlight={selectedFlight}
            setSelectedFlight={setSelectedFlight}
            selectedHotel={selectedHotel}
            setSelectedHotel={setSelectedHotel}
            onEmail={onEmail}
          />
        )}

    </main>
  );
}

/* ============================================================
   INR / BUDGET HELPERS
============================================================ */

function getBudgetData(info) {
  if (!info || typeof info !== "object") {
    return {
      flight: null,
      hotel: null,
      food: null,
      transport: null,
      activities: null,
      total: null,
      percentages: {},
      exchangeRate: null,
    };
  }

  const automaticBudget = info.budget || {};
  const breakdown = automaticBudget.breakdown || {};

  const tripEstimate = info.trip_estimate || {};

  return {
    flight:
      breakdown.flights ??
      tripEstimate.flight ??
      info.flight_cost ??
      null,

    hotel:
      breakdown.hotels ??
      tripEstimate.hotel ??
      info.hotel_cost ??
      null,

    food:
      breakdown.food ??
      null,

    transport:
      breakdown.transportation ??
      breakdown.transport ??
      null,

    activities:
      breakdown.activities ??
      null,

    total:
      automaticBudget.estimated_cost ??
      tripEstimate.total ??
      info.total_budget ??
      info.estimated_total ??
      null,

    percentages:
      automaticBudget.percentages || {},

    exchangeRate:
      automaticBudget.exchange_rate ?? null,
  };
}

function formatINR(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  if (typeof value === "number") {
    return `₹${Math.round(value).toLocaleString(
      "en-IN"
    )}`;
  }

  const text = String(value).trim();

  if (
    text.includes("₹") ||
    text.toLowerCase().includes("inr")
  ) {
    return text
      .replace(/\bINR\b/gi, "₹")
      .replace(/₹\s*/g, "₹");
  }

  const numericMatch = text
    .replace(/,/g, "")
    .match(/(\d+(?:\.\d+)?)/);

  if (!numericMatch) {
    return text;
  }

  const amount = Number(numericMatch[1]);

  if (!Number.isFinite(amount)) {
    return text;
  }

  if (
    text.includes("$") ||
    text.toLowerCase().includes("usd")
  ) {
    const USD_TO_INR = 88;

    return `₹${Math.round(
      amount * USD_TO_INR
    ).toLocaleString("en-IN")}`;
  }

  return `₹${Math.round(
    amount
  ).toLocaleString("en-IN")}`;
}

function hasBudgetValues(budget) {
  return Object.values(budget).some(
    (value) =>
      value !== null &&
      value !== undefined &&
      value !== "" &&
      !(
        typeof value === "object" &&
        Object.keys(value).length === 0
      )
  );
}

/* ============================================================
   WEATHER HELPERS
============================================================ */

function getWeatherData(info) {
  if (!info || typeof info !== "object") {
    return null;
  }

  const weather =
    info.weather ||
    info.weather_forecast ||
    info.forecast ||
    info.destination_weather ||
    null;

  if (!weather) {
    return null;
  }

  if (Array.isArray(weather)) {
    return {
      location:
        info.destination ||
        info.destination_city ||
        info.to ||
        "Destination",

      forecast: weather,
    };
  }

  if (typeof weather === "object") {
    return {
      ...weather,

      location:
        weather.location ||
        weather.city ||
        info.destination ||
        info.destination_city ||
        info.to ||
        "Destination",

      forecast:
        weather.forecast ||
        weather.daily ||
        weather.days ||
        weather.data ||
        [],
    };
  }

  return null;
}

function getWeatherValue(item, keys) {
  if (!item || typeof item !== "object") {
    return null;
  }

  for (const key of keys) {
    if (
      item[key] !== undefined &&
      item[key] !== null &&
      item[key] !== ""
    ) {
      return item[key];
    }
  }

  return null;
}

/* ============================================================
   TRAVEL RESULTS
============================================================ */

function TravelResults({
  travelData,
  selectedFlight,
  setSelectedFlight,
  selectedHotel,
  setSelectedHotel,
  onEmail,
}) {
  const info = travelData?.travel_info;

  if (!info) return null;

  // ==========================================================
  // MARKDOWN RESPONSE
  // ==========================================================

  if (typeof info === "string") {
    return (
      <section className="results">

        <div className="results-header">

          <div>

            <div className="results-eyebrow">
              VOYARA AI
            </div>

            <h2>
              Your journey is ready
            </h2>

            <p>
              Generated by your Voyara
              travel agent
            </p>

          </div>

        </div>

        <div className="results-grid">

          <div className="results-main">

            <MarkdownTravelResult
              text={info}
            />

          </div>

          <aside className="journey-sidebar">

            <div className="ai-card">

              <div className="ai-card-header">

                <div className="ai-icon">
                  ✦
                </div>

                <div>

                  <span>
                    VOYARA AI
                  </span>

                  <strong>
                    Travel Plan
                  </strong>

                </div>

              </div>

              <p>
                Your personalized journey
                has been created by
                Voyara AI.
              </p>

              <button
                className="email-itinerary-button"
                onClick={onEmail}
              >
                <span>✉</span>
                Send itinerary by email
              </button>

            </div>

          </aside>

        </div>

      </section>
    );
  }

  // ==========================================================
  // STRUCTURED JSON RESPONSE
  // ==========================================================

  const flights =
    info.flights ||
    info.flight_options ||
    [];

  const hotels =
    info.hotels ||
    info.hotel_options ||
    [];

  const itinerary =
    info.daily_itinerary ||
    info.itinerary ||
    info.days ||
    info.plan ||
    [];

  const budget = getBudgetData(info);

  const weather = getWeatherData(info);

  const hasBudget = hasBudgetValues(budget);

  const summary =
    info.summary ||
    info.overview ||
    info.description ||
    "";

  return (
    <section className="results">

      <div className="results-header">

        <div>

          <div className="results-eyebrow">
            VOYARA AI
          </div>

          <h2>
            Your journey is ready
          </h2>

          <p>
            Generated by your Voyara
            travel agent
          </p>

        </div>

      </div>

      <div className="results-grid">

        <div className="results-main">

          {/* =================================================
              SUMMARY
          ================================================= */}

          {summary && (
            <div className="summary-card">

              <p>
                {summary}
              </p>

            </div>
          )}

          {/* =================================================
              FLIGHTS
          ================================================= */}

          {flights.length > 0 && (
            <>
              <div className="section-heading">

                <div>

                  <span className="section-number">
                    01
                  </span>

                  <h3>
                    Flights
                  </h3>

                </div>

                <span>
                  {flights.length} option
                  {flights.length !== 1
                    ? "s"
                    : ""}
                </span>

              </div>

              <div className="flight-list">

                {flights.map(
                  (flight, index) => (
                    <FlightCard
                      key={
                        flight.id ||
                        `${flight.airline}-${index}`
                      }
                      flight={flight}
                      selected={
                        selectedFlight === index
                      }
                      onSelect={() =>
                        setSelectedFlight(index)
                      }
                    />
                  )
                )}

              </div>
            </>
          )}

          {/* =================================================
              HOTELS
          ================================================= */}

          {hotels.length > 0 && (
            <>
              <div className="section-heading hotel-heading">

                <div>

                  <span className="section-number">
                    02
                  </span>

                  <h3>
                    Stay
                  </h3>

                </div>

                <span>
                  Curated for you
                </span>

              </div>

              <div className="hotel-list">

                {hotels.map(
                  (hotel, index) => (
                    <HotelCard
                      key={
                        hotel.id ||
                        `${hotel.name}-${index}`
                      }
                      hotel={hotel}
                      selected={
                        selectedHotel === index
                      }
                      onSelect={() =>
                        setSelectedHotel(index)
                      }
                    />
                  )
                )}

              </div>
            </>
          )}

          {/* =================================================
              TRIP BUDGET
          ================================================= */}

          {hasBudget && (
            <section className="voyara-budget-section">

              <div className="section-heading">

                <div>

                  <span className="section-number">
                    03
                  </span>

                  <h3>
                    Trip Budget
                  </h3>

                </div>

                <span>
                  Estimated in INR
                </span>

              </div>

              <div className="budget-card">

                <div className="budget-header">

                  <div>

                    <span className="budget-eyebrow">
                      VOYARA ESTIMATE
                    </span>

                    <h3>
                      Plan your spending
                    </h3>

                    <p>
                      Estimated trip cost including
                      flights, stay and daily expenses.
                    </p>

                  </div>

                  <div className="budget-total">

                    <span>
                      Estimated total
                    </span>

                    <strong>
                      {formatINR(
                        budget.total
                      )}
                    </strong>

                  </div>

                </div>

                <div className="budget-grid">

                  {budget.flight !== null &&
                    budget.flight !== undefined && (

                      <div className="budget-item">

                        <div className="budget-item-icon">
                          ✈
                        </div>

                        <div>

                          <span>
                            Flights
                          </span>

                          <strong>
                            {formatINR(
                              budget.flight
                            )}
                          </strong>

                        </div>

                      </div>

                    )}

                  {budget.hotel !== null &&
                    budget.hotel !== undefined && (

                      <div className="budget-item">

                        <div className="budget-item-icon">
                          🏨
                        </div>

                        <div>

                          <span>
                            Hotels
                          </span>

                          <strong>
                            {formatINR(
                              budget.hotel
                            )}
                          </strong>

                        </div>

                      </div>

                    )}

                  {budget.food !== null &&
                    budget.food !== undefined && (

                      <div className="budget-item">

                        <div className="budget-item-icon">
                          🍴
                        </div>

                        <div>

                          <span>
                            Food
                          </span>

                          <strong>
                            {formatINR(
                              budget.food
                            )}
                          </strong>

                        </div>

                      </div>

                    )}

                  {budget.transport !== null &&
                    budget.transport !== undefined && (

                      <div className="budget-item">

                        <div className="budget-item-icon">
                          🚕
                        </div>

                        <div>

                          <span>
                            Local transport
                          </span>

                          <strong>
                            {formatINR(
                              budget.transport
                            )}
                          </strong>

                        </div>

                      </div>

                    )}

                  {budget.activities !== null &&
                    budget.activities !== undefined && (

                      <div className="budget-item">

                        <div className="budget-item-icon">
                          🎟️
                        </div>

                        <div>

                          <span>
                            Activities
                          </span>

                          <strong>
                            {formatINR(
                              budget.activities
                            )}
                          </strong>

                        </div>

                      </div>

                    )}

                </div>

                {Object.keys(
                  budget.percentages
                ).length > 0 && (

                  <div className="budget-percentages">

                    <div className="budget-percentage-header">

                      <strong>
                        Spending distribution
                      </strong>

                      <span>
                        Based on estimated trip cost
                      </span>

                    </div>

                    <div className="budget-percentage-list">

                      {[
                        {
                          key: "flights",
                          label: "Flights",
                          icon: "✈",
                        },
                        {
                          key: "hotels",
                          label: "Hotels",
                          icon: "🏨",
                        },
                        {
                          key: "food",
                          label: "Food",
                          icon: "🍴",
                        },
                        {
                          key: "transportation",
                          label: "Transport",
                          icon: "🚕",
                        },
                        {
                          key: "activities",
                          label: "Activities",
                          icon: "🎟️",
                        },
                      ].map((item) => {

                        const percentage =
                          budget.percentages[
                            item.key
                          ];

                        if (
                          percentage ===
                            undefined ||
                          percentage === null
                        ) {
                          return null;
                        }

                        return (
                          <div
                            className="budget-percentage-row"
                            key={item.key}
                          >

                            <div className="budget-percentage-label">

                              <span>
                                {item.icon}
                              </span>

                              <strong>
                                {item.label}
                              </strong>

                            </div>

                            <div className="budget-progress">

                              <div className="budget-progress-track">

                                <div
                                  className="budget-progress-fill"
                                  style={{
                                    width: `${Math.min(
                                      Number(
                                        percentage
                                      ),
                                      100
                                    )}%`,
                                  }}
                                ></div>

                              </div>

                              <span>
                                {percentage}%
                              </span>

                            </div>

                          </div>
                        );
                      })}

                    </div>

                  </div>
                )}

                {budget.exchangeRate && (

                  <div className="budget-exchange-rate">

                    <span>
                      💱
                    </span>

                    <span>
                      Planning exchange rate:
                    </span>

                    <strong>
                      1 USD = ₹
                      {budget.exchangeRate}
                    </strong>

                  </div>

                )}

                <div className="budget-note">

                  <span>
                    ₹
                  </span>

                  <div>

                    <strong>
                      Planning estimate
                    </strong>

                    <p>
                      Food, local transportation
                      and activities use estimated
                      daily planning allowances.
                      Actual prices may vary depending
                      on availability, season and
                      booking time.
                    </p>

                  </div>

                </div>

              </div>

            </section>
          )}

          {/* =================================================
              WEATHER
          ================================================= */}

          {weather &&
            weather.forecast &&
            weather.forecast.length > 0 && (

              <section className="voyara-weather-section">

                <div className="section-heading">

                  <div>

                    <span className="section-number">
                      04
                    </span>

                    <h3>
                      Weather
                    </h3>

                  </div>

                  <span>
                    {weather.location}
                  </span>

                </div>

                <div className="weather-card">

                  <div className="weather-card-header">

                    <div>

                      <span className="weather-eyebrow">
                        TRAVEL FORECAST
                      </span>

                      <h3>
                        Weather in{" "}
                        {weather.location}
                      </h3>

                      <p>
                        Check the expected
                        conditions while planning
                        each day of your journey.
                      </p>

                    </div>

                    <div className="weather-main-icon">
                      ☀️
                    </div>

                  </div>

                  <div className="weather-list">

                    {weather.forecast.map(
                      (day, index) => {

                        const date =
                          getWeatherValue(
                            day,
                            [
                              "date",
                              "day",
                              "datetime",
                            ]
                          );

                        const condition =
                          getWeatherValue(
                            day,
                            [
                              "condition",
                              "description",
                              "weather",
                              "summary",
                              "text",
                            ]
                          );

                        const temperature =
                          getWeatherValue(
                            day,
                            [
                              "temperature",
                              "temp",
                              "temperature_c",
                              "temp_c",
                              "max_temperature",
                            ]
                          );

                        const minTemperature =
                          getWeatherValue(
                            day,
                            [
                              "min_temperature",
                              "min_temp",
                              "min_temp_c",
                              "low",
                            ]
                          );

                        const maxTemperature =
                          getWeatherValue(
                            day,
                            [
                              "max_temperature",
                              "max_temp",
                              "max_temp_c",
                              "high",
                            ]
                          );

                        const rain =
                          getWeatherValue(
                            day,
                            [
                              "rain",
                              "rain_chance",
                              "precipitation",
                              "precipitation_probability",
                            ]
                          );

                        const humidity =
                          getWeatherValue(
                            day,
                            [
                              "humidity",
                            ]
                          );

                        const conditionText =
                          String(
                            condition || ""
                          ).toLowerCase();

                        let weatherIcon =
                          "☀️";

                        if (
                          conditionText.includes(
                            "rain"
                          ) ||
                          conditionText.includes(
                            "shower"
                          )
                        ) {
                          weatherIcon = "🌧️";
                        } else if (
                          conditionText.includes(
                            "cloud"
                          ) ||
                          conditionText.includes(
                            "overcast"
                          )
                        ) {
                          weatherIcon = "⛅";
                        } else if (
                          conditionText.includes(
                            "storm"
                          ) ||
                          conditionText.includes(
                            "thunder"
                          )
                        ) {
                          weatherIcon = "⛈️";
                        }

                        return (
                          <div
                            className="weather-day"
                            key={index}
                          >

                            <div className="weather-day-date">

                              <span>
                                DAY{" "}
                                {String(
                                  index + 1
                                ).padStart(
                                  2,
                                  "0"
                                )}
                              </span>

                              <strong>
                                {date ||
                                  "Travel day"}
                              </strong>

                            </div>

                            <div className="weather-condition">

                              <div className="weather-condition-icon">
                                {weatherIcon}
                              </div>

                              <div>

                                <strong>
                                  {condition ||
                                    "Weather forecast"}
                                </strong>

                                {temperature && (
                                  <span>
                                    {temperature}
                                  </span>
                                )}

                              </div>

                            </div>

                            <div className="weather-details">

                              {(minTemperature ||
                                maxTemperature) && (

                                <div>

                                  <span>
                                    Temperature
                                  </span>

                                  <strong>
                                    {minTemperature ||
                                      "—"}
                                    {" "}
                                    –
                                    {" "}
                                    {maxTemperature ||
                                      "—"}
                                  </strong>

                                </div>

                              )}

                              {rain !== null &&
                                rain !== undefined && (

                                  <div>

                                    <span>
                                      Rain
                                    </span>

                                    <strong>
                                      {rain}
                                      {String(
                                        rain
                                      ).includes(
                                        "%"
                                      )
                                        ? ""
                                        : "%"}
                                    </strong>

                                  </div>

                                )}

                              {humidity !== null &&
                                humidity !==
                                  undefined && (

                                  <div>

                                    <span>
                                      Humidity
                                    </span>

                                    <strong>
                                      {humidity}
                                      {String(
                                        humidity
                                      ).includes(
                                        "%"
                                      )
                                        ? ""
                                        : "%"}
                                    </strong>

                                  </div>

                                )}

                            </div>

                          </div>
                        );
                      }
                    )}

                  </div>

                </div>

              </section>
            )}

          {/* =================================================
              DAY-BY-DAY JOURNEY
          ================================================= */}

          {itinerary.length > 0 && (
            <section className="voyara-day-plan-section">

              <div className="section-heading">

                <div>

                  <span className="section-number">
                    05
                  </span>

                  <h3>
                    Day-by-Day Journey
                  </h3>

                </div>

                <span>
                  {itinerary.length} day
                  {itinerary.length !== 1
                    ? "s"
                    : ""}
                </span>

              </div>

              <div className="voyara-day-plan">

                {itinerary.map(
                  (day, index) => {

                    const activities =
                      day.activities ||
                      day.items ||
                      day.plans ||
                      day.highlights ||
                      [];

                    const activityList =
                      Array.isArray(
                        activities
                      )
                        ? activities
                        : [activities];

                    const dayNumber =
                      String(
                        index + 1
                      ).padStart(
                        2,
                        "0"
                      );

                    return (
                      <div
                        className="voyara-day-card"
                        key={
                          day.day ||
                          day.date ||
                          index
                        }
                      >

                        <div className="voyara-day-number">

                          <span>
                            DAY
                          </span>

                          <strong>
                            {dayNumber}
                          </strong>

                        </div>

                        <div className="voyara-day-content">

                          <div className="voyara-day-top">

                            <div>

                              <div className="voyara-day-label">
                                DAY{" "}
                                {dayNumber}
                              </div>

                              <h4>
                                {day.title ||
                                  day.name ||
                                  `Day ${
                                    index + 1
                                  }`}
                              </h4>

                              {day.date && (
                                <span className="voyara-day-date">
                                  {day.date}
                                </span>
                              )}

                            </div>

                          </div>

                          {day.description && (
                            <p className="voyara-day-description">
                              {day.description}
                            </p>
                          )}

                          {activityList.length > 0 && (
                            <div className="voyara-activities">

                              {activityList.map(
                                (
                                  activity,
                                  activityIndex
                                ) => {

                                  if (
                                    activity ===
                                      null ||
                                    activity ===
                                      undefined
                                  ) {
                                    return null;
                                  }

                                  if (
                                    typeof activity ===
                                    "object"
                                  ) {

                                    return (
                                      <div
                                        className="voyara-activity"
                                        key={
                                          activityIndex
                                        }
                                      >

                                        <div className="activity-check">
                                          ✓
                                        </div>

                                        <div className="activity-content">

                                          <strong>
                                            {activity.title ||
                                              activity.name ||
                                              activity.activity ||
                                              `Activity ${
                                                activityIndex +
                                                1
                                              }`}
                                          </strong>

                                          {activity.description && (
                                            <p>
                                              {
                                                activity.description
                                              }
                                            </p>
                                          )}

                                        </div>

                                      </div>
                                    );
                                  }

                                  return (
                                    <div
                                      className="voyara-activity"
                                      key={
                                        activityIndex
                                      }
                                    >

                                      <div className="activity-check">
                                        ✓
                                      </div>

                                      <div className="activity-content">

                                        <p>
                                          {activity}
                                        </p>

                                      </div>

                                    </div>
                                  );
                                }
                              )}

                            </div>
                          )}

                        </div>

                      </div>
                    );
                  }
                )}

              </div>

            </section>
          )}

        </div>

        {/* =================================================
            SIDEBAR
        ================================================= */}

        <aside className="journey-sidebar">

          {itinerary.length > 0 && (
            <div className="ai-card">

              <div className="ai-card-header">

                <div className="ai-icon">
                  ✦
                </div>

                <div>

                  <span>
                    VOYARA AI
                  </span>

                  <strong>
                    Your itinerary
                  </strong>

                </div>

              </div>

              <div className="itinerary-list">

                {itinerary.map(
                  (day, index) => (

                    <div
                      className="itinerary-day"
                      key={
                        day.day ||
                        index
                      }
                    >

                      <div className="day-number">
                        {String(
                          index + 1
                        ).padStart(2, "0")}
                      </div>

                      <div>

                        <strong>
                          {day.title ||
                            day.name ||
                            `Day ${
                              index + 1
                            }`}
                        </strong>

                        <ul>

                          {(
                            day.activities ||
                            day.items ||
                            day.plans ||
                            []
                          ).map(
                            (
                              activity,
                              i
                            ) => (
                              <li key={i}>

                                {typeof activity ===
                                "object"
                                  ? activity.title ||
                                    activity.name ||
                                    activity.activity ||
                                    "Activity"
                                  : activity}

                              </li>
                            )
                          )}

                        </ul>

                      </div>

                    </div>

                  )
                )}

              </div>

              <button
                className="email-itinerary-button"
                onClick={onEmail}
              >
                <span>
                  ✉
                </span>

                Send itinerary by email

              </button>

            </div>
          )}

          {!itinerary.length && (
            <div className="ai-card">

              <div className="ai-card-header">

                <div className="ai-icon">
                  ✦
                </div>

                <div>

                  <span>
                    VOYARA AI
                  </span>

                  <strong>
                    Travel Plan
                  </strong>

                </div>

              </div>

              <p>
                Your personalized travel
                plan is ready.
              </p>

              <button
                className="email-itinerary-button"
                onClick={onEmail}
              >
                <span>
                  ✉
                </span>

                Send itinerary by email

              </button>

            </div>
          )}

        </aside>

      </div>

    </section>
  );
}

/* ============================================================
   MARKDOWN TRAVEL RESULT
============================================================ */

function MarkdownTravelResult({ text }) {

  const clean = (value = "") => {
    return value
      .replace(/\u202f/g, " ")
      .replace(/\u00a0/g, " ")
      .replace(/\*\*\*/g, "")
      .replace(/\*\*/g, "")
      .replace(/\*/g, "")
      .replace(/`/g, "")
      .trim();
  };

  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className="travel-result-container">

      {lines.map((line, index) => {

        if (
          line.startsWith("# ") ||
          line.startsWith("## ") ||
          line.startsWith("### ")
        ) {

          const heading = clean(
            line
              .replace(/^###\s*/, "")
              .replace(/^##\s*/, "")
              .replace(/^#\s*/, "")
          );

          return (
            <div
              className="travel-result-heading"
              key={index}
            >
              {heading}
            </div>
          );
        }

        if (line.startsWith("|")) {

          if (
            line.includes("---") ||
            line.includes("Airline |") ||
            line.includes("Hotel |")
          ) {
            return null;
          }

          const cells = line
            .split("|")
            .map((cell) => clean(cell))
            .filter(Boolean);

          if (!cells.length) {
            return null;
          }

          return (
            <div
              className="travel-table-row"
              key={index}
            >

              {cells.map(
                (cell, cellIndex) => (
                  <div
                    className="travel-table-cell"
                    key={cellIndex}
                  >
                    {cell}
                  </div>
                )
              )}

            </div>
          );
        }

        if (
          line.startsWith("Route:") ||
          line.startsWith("Dates:") ||
          line.startsWith("Travelers:") ||
          line.startsWith("Class:")
        ) {

          const parts = line.split(":");

          const label = parts.shift();

          const value = parts.join(":");

          return (
            <div
              className="travel-info-row"
              key={index}
            >

              <span>
                {clean(label)}
              </span>

              <strong>
                {clean(value)}
              </strong>

            </div>
          );
        }

        if (
          line.includes("Recommended Flight") ||
          line.includes("Recommended Stay")
        ) {

          return (
            <div
              className="recommended-title"
              key={index}
            >
              ★ {clean(line)}
            </div>
          );
        }

        if (
          line.startsWith(
            "Why recommended:"
          )
        ) {

          return (
            <div
              className="recommended-description"
              key={index}
            >
              {clean(line)}
            </div>
          );
        }

        if (
          line.startsWith("Flight:") ||
          line.startsWith("Hotel:") ||
          line.startsWith("Estimated Total:")
        ) {

          const parts = line.split(":");

          const label = parts.shift();

          const value = parts.join(":");

          const isTotal =
            line.startsWith(
              "Estimated Total:"
            );

          return (
            <div
              className={
                isTotal
                  ? "travel-total-row"
                  : "travel-price-row"
              }
              key={index}
            >

              <span>
                {clean(label)}
              </span>

              <strong>
                {formatINR(
                  clean(value)
                )}
              </strong>

            </div>
          );
        }

        if (
          line.startsWith("![") ||
          line.startsWith("[Book Flight]") ||
          line.startsWith("[Visit Hotel]")
        ) {
          return null;
        }

        return (
          <p
            className="travel-result-text"
            key={index}
          >
            {clean(line)}
          </p>
        );
      })}

    </div>
  );
}

/* ============================================================
   FLIGHT CARD
============================================================ */

function FlightCard({
  flight,
  selected,
  onSelect,
}) {

  const logo =
    flight.logo ||
    (flight.airline
      ? flight.airline
          .slice(0, 2)
          .toUpperCase()
      : "✈");

  return (
    <div
      className={`flight-card ${
        selected ? "selected" : ""
      }`}
      onClick={onSelect}
    >

      <div className="flight-top">

        <div className="airline">

          <div className="airline-logo">
            {logo}
          </div>

          <div>

            <strong>
              {flight.airline ||
                "Airline"}
            </strong>

            {flight.tag && (
              <span>
                {flight.tag}
              </span>
            )}

          </div>

        </div>

        {selected && (
          <div className="selected-label">
            ✓ Selected
          </div>
        )}

      </div>

      <div className="flight-route">

        <div>

          <strong>
            {flight.departure ||
              "--:--"}
          </strong>

          <span>
            {flight.from ||
              flight.origin ||
              ""}
          </span>

        </div>

        <div className="flight-line">

          <span>
            {flight.duration || ""}
          </span>

          <div>
            <i></i>
            <b></b>
            <i></i>
          </div>

          <span>
            {flight.stops ||
              "Direct"}
          </span>

        </div>

        <div>

          <strong>
            {flight.arrival ||
              "--:--"}
          </strong>

          <span>
            {flight.to ||
              flight.destination ||
              ""}
          </span>

        </div>

      </div>

      <div className="flight-bottom">

        <span>
          {flight.notes ||
            "Economy · Carry-on included"}
        </span>

        <strong>
          {formatINR(
            flight.price
          )}
        </strong>

      </div>

    </div>
  );
}

/* ============================================================
   HOTEL CARD
============================================================ */

function HotelCard({
  hotel,
  selected,
  onSelect,
}) {

  return (
    <div
      className={`hotel-card ${
        selected ? "selected" : ""
      }`}
      onClick={onSelect}
    >

      <div className="hotel-info">

        <div className="hotel-card-top">

          <div>

            {hotel.rating && (
              <div className="hotel-rating">

                ★ {hotel.rating}

                {hotel.reviews && (
                  <span>
                    {" "}
                    ({hotel.reviews})
                  </span>
                )}

              </div>
            )}

            <h4>
              {hotel.name || "Hotel"}
            </h4>

            {hotel.location && (
              <p className="hotel-location">
                📍 {hotel.location}
              </p>
            )}

          </div>

          {selected && (
            <span className="selected-label">
              ✓ Selected
            </span>
          )}

        </div>

        <div className="hotel-details">

          {hotel.price && (
            <div className="hotel-detail">

              <span>
                Price / night
              </span>

              <strong>
                {formatINR(
                  hotel.price
                )}
              </strong>

            </div>
          )}

          {hotel.total && (
            <div className="hotel-detail">

              <span>
                Total stay
              </span>

              <strong>
                {formatINR(
                  hotel.total
                )}
              </strong>

            </div>
          )}

          {hotel.amenities && (
            <div className="hotel-detail">

              <span>
                Amenities
              </span>

              <strong>
                {hotel.amenities}
              </strong>

            </div>
          )}

        </div>

      </div>

    </div>
  );
}

/* ============================================================
   AUTH MODAL
============================================================ */

function AuthModal({
  onClose,
  onLogin,
  onRegister,
}) {

  const [mode, setMode] = useState("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isLogin = mode === "login";

  const handleSubmit = async () => {

    setError("");

    const cleanEmail = email.trim();

    if (!cleanEmail) {
      setError(
        "Please enter your email address."
      );
      return;
    }

    if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
        cleanEmail
      )
    ) {
      setError(
        "Please enter a valid email address."
      );
      return;
    }

    if (!isLogin && !name.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (!password) {
      setError("Please enter your password.");
      return;
    }

    if (password.length < 6) {
      setError(
        "Password must be at least 6 characters."
      );
      return;
    }

    try {

      setLoading(true);

      if (isLogin) {

        await onLogin(
          cleanEmail,
          password
        );

      } else {

        await onRegister(
          name,
          cleanEmail,
          password
        );

      }

    } catch (err) {

      setError(
        err.message ||
          "Something went wrong. Please try again."
      );

    } finally {

      setLoading(false);

    }
  };

  return (
    <div className="modal-backdrop">

      <div className="auth-modal">

        <button
          className="modal-close"
          onClick={onClose}
          disabled={loading}
        >
          ×
        </button>

        <div className="auth-brand">

          <div className="auth-logo">
            V
          </div>

          <span>
            voyara
          </span>

        </div>

        <div className="auth-content">

          <div className="auth-spark">
            ✦
          </div>

          <h2>
            {isLogin
              ? "Welcome back to Voyara"
              : "Create your Voyara account"}
          </h2>

          <p>
            {isLogin
              ? "Sign in to continue your personalized AI travel experience."
              : "Create an account and start planning your next journey with Voyara AI."}
          </p>

          {!isLogin && (
            <>
              <label className="auth-field-label">
                Name
              </label>

              <input
                type="text"
                className="auth-email-input"
                placeholder="Enter your name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setError("");
                }}
                disabled={loading}
              />
            </>
          )}

          <label className="auth-field-label">
            Email
          </label>

          <input
            type="email"
            className="auth-email-input"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError("");
            }}
            disabled={loading}
          />

          <label className="auth-field-label">
            Password
          </label>

          <input
            type="password"
            className="auth-email-input"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError("");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSubmit();
              }
            }}
            disabled={loading}
          />

          {error && (
            <p className="auth-error">
              {error}
            </p>
          )}

          <button
            className="google-button"
            onClick={handleSubmit}
            disabled={loading}
          >

            {loading ? (
              <>
                <span className="button-loader"></span>

                {isLogin
                  ? "Signing in..."
                  : "Creating account..."}
              </>
            ) : (
              <>
                <span className="google-letter">
                  →
                </span>

                <span>
                  {isLogin
                    ? "Sign in"
                    : "Create account"}
                </span>
              </>
            )}

          </button>

          <div className="auth-divider">

            <span>
              secure authentication
            </span>

          </div>

          <div className="auth-features">

            <div>
              <span>✦</span>
              AI-powered trip planning
            </div>

            <div>
              <span>✓</span>
              Personalized travel recommendations
            </div>

            <div>
              <span>✉</span>
              Save and email your itinerary
            </div>

          </div>

          <div className="auth-switch">

            {isLogin ? (
              <>
                <span>
                  Don't have an account?
                </span>

                <button
                  type="button"
                  onClick={() => {
                    setMode("register");
                    setError("");
                  }}
                  disabled={loading}
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                <span>
                  Already have an account?
                </span>

                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError("");
                  }}
                  disabled={loading}
                >
                  Sign in
                </button>
              </>
            )}

          </div>

          <small>
            By continuing, you agree to
            Voyara's Terms and Privacy Policy.
          </small>

        </div>

      </div>

    </div>
  );
}

/* ============================================================
   EMAIL MODAL
============================================================ */

function EmailModal({
  user,
  sendingEmail,
  emailSent,
  onSend,
  onClose,
  selectedFlight,
  selectedHotel,
  travelData,
}) {

  const info = travelData?.travel_info;

  const isStructured =
    info &&
    typeof info === "object" &&
    !Array.isArray(info);

  const flights = isStructured
    ? info.flights ||
      info.flight_options ||
      []
    : [];

  const hotels = isStructured
    ? info.hotels ||
      info.hotel_options ||
      []
    : [];

  const itinerary = isStructured
    ? info.daily_itinerary ||
      info.itinerary ||
      info.days ||
      info.plan ||
      []
    : [];

  const budget = isStructured
    ? getBudgetData(info)
    : {
        flight: null,
        hotel: null,
        food: null,
        transport: null,
        activities: null,
        total: null,
        percentages: {},
        exchangeRate: null,
      };

  return (
    <div className="modal-backdrop">

      <div className="email-modal">

        <button
          className="modal-close"
          onClick={onClose}
          disabled={sendingEmail}
        >
          ×
        </button>

        {!emailSent ? (
          <>

            <div className="email-header">

              <div className="email-icon">
                ✉
              </div>

              <div>

                <span>
                  TRAVEL ITINERARY
                </span>

                <h2>
                  Send your journey
                </h2>

              </div>

            </div>

            <div className="email-form">

              <label>
                Recipient email
              </label>

              <input
                type="email"
                value={user?.email || ""}
                readOnly
                placeholder="Your email"
              />

              <label>
                Subject
              </label>

              <input
                type="text"
                value="Your Voyara Travel Itinerary"
                readOnly
              />

              <label>
                Preview
              </label>

              <div className="email-preview">

                <div className="preview-title">
                  Your journey is ready ✈
                </div>

                <p>
                  Here's your personalized
                  travel plan created by
                  Voyara AI.
                </p>

                {flights.length > 0 && (
                  <div className="preview-row">

                    <span>
                      Flight
                    </span>

                    <strong>
                      {selectedFlight !== null &&
                      flights[selectedFlight]
                        ? flights[
                            selectedFlight
                          ].airline
                        : "Best available flight"}
                    </strong>

                  </div>
                )}

                {hotels.length > 0 && (
                  <div className="preview-row">

                    <span>
                      Hotel
                    </span>

                    <strong>
                      {selectedHotel !== null &&
                      hotels[selectedHotel]
                        ? hotels[
                            selectedHotel
                          ].name
                        : "Recommended hotel"}
                    </strong>

                  </div>
                )}

                {budget.total !== null &&
                  budget.total !== undefined && (

                    <div className="preview-row">

                      <span>
                        Estimated budget
                      </span>

                      <strong>
                        {formatINR(
                          budget.total
                        )}
                      </strong>

                    </div>

                  )}

                {budget.flight !== null &&
                  budget.hotel !== null && (

                    <div className="preview-itinerary">

                      <strong>
                        Budget breakdown
                      </strong>

                      <p>

                        Flights:{" "}
                        {formatINR(
                          budget.flight
                        )}
                        <br />

                        Hotels:{" "}
                        {formatINR(
                          budget.hotel
                        )}

                        {budget.food !== null && (
                          <>
                            <br />
                            Food:{" "}
                            {formatINR(
                              budget.food
                            )}
                          </>
                        )}

                        {budget.transport !== null && (
                          <>
                            <br />
                            Transport:{" "}
                            {formatINR(
                              budget.transport
                            )}
                          </>
                        )}

                        {budget.activities !== null && (
                          <>
                            <br />
                            Activities:{" "}
                            {formatINR(
                              budget.activities
                            )}
                          </>
                        )}

                      </p>

                    </div>

                  )}

                {itinerary.length > 0 && (
                  <div className="preview-itinerary">

                    <strong>
                      AI Itinerary
                    </strong>

                    <p>

                      {itinerary.map(
                        (day, i) => (

                          <span key={i}>

                            Day{" "}
                            {day.day ||
                              i + 1}{" "}
                            —{" "}
                            {day.title ||
                              day.name ||
                              "Plan"}

                            <br />

                          </span>

                        )
                      )}

                    </p>

                  </div>
                )}

                {typeof info === "string" && (
                  <div className="preview-itinerary">

                    <strong>
                      Voyara Travel Plan
                    </strong>

                    <p>
                      Your complete
                      AI-generated travel
                      itinerary will be
                      included in the email.
                    </p>

                  </div>
                )}

              </div>

              <button
                className="send-email-button"
                onClick={onSend}
                disabled={
                  !user?.email ||
                  sendingEmail
                }
              >

                {sendingEmail ? (
                  <>
                    <span className="button-loader"></span>
                    Sending...
                  </>
                ) : (
                  <>
                    Send itinerary
                    <span>→</span>
                  </>
                )}

              </button>

            </div>

          </>

        ) : (

          <div className="email-success">

            <div className="success-circle">
              ✓
            </div>

            <h2>
              Itinerary sent!
            </h2>

            <p>
              Your Voyara travel plan
              has been sent to{" "}
              <strong>
                {user?.email}
              </strong>.
            </p>

          </div>

        )}

      </div>

    </div>
  );
}

export default App;

