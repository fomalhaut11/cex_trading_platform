# Market Data Schema

Market data contains observable market facts. IV, Greeks, smiles and volatility
surfaces belong to the registered feature domain. Venue-published option
analytics may be recorded only as explicitly labelled reference observations.

Canonical objects:

-   MarketTrade
-   AggregateTrade
-   OrderBookDelta
-   PartialBookFrame
-   KlineUpdate
-   FundingUpdate
-   BestBidAsk
-   MarkPriceUpdate
-   IndexPriceUpdate
-   OpenInterestUpdate
-   VenueOptionAnalyticsUpdate

All objects require:

-   event_time
-   receive_time
-   instrument_id
-   schema_version

Canonical events compose immutable `EventMetadata` and use exact fixed-point
prices, quantities and venue rates. Order-book deltas carry explicit sequence
ranges. A zero delta quantity deletes a level; snapshot levels must be positive.

Venue-native JSON, symbols and error codes do not cross the adapter boundary.
