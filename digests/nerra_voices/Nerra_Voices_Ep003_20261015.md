# Nerra Voices

> **A scalper who once handled a tenth of E-mini volume rebuilt a durable edge by reading iceberg orders and stop runs after algorithms erased his original speed advantage, then teaches the resulting rule set to retail traders.**

*Episode 3 · October 15, 2026*

**What You Need to Know:** Scott Pulcini once lost $800,000 in minutes on two separate days after breaching his own $100,000 daily loss limit instead of stopping. He rebuilt a durable edge after algorithms erased his original speed advantage by shifting from visible counterparties to reading stop runs and iceberg orders through CME MBO data on Bookmap, then codified the resulting rules into courses for retail traders.

---

### Listen

[Listen to the full conversation](https://audio.nerranetwork.com/nerra_voices/raw/a3d927d4-a1a4-489c-a954-1b846948554d_edit_20261007232058.mp3)

---

### About Scott Pulcini

**Futures trader**

Scott Pulcini joined Mira for this conversation.

---

### What we talked about

- Scott once averaged 50,000 contracts a day—roughly 10 percent of E-mini S&P volume—by placing orders throughout the book and scalping around them while seeing every counterparty.
- After house numbers vanished, he adopted 2016 CME MBO data that reveals iceberg orders with certainty and treats them as the next-best proxy for where large entities are accumulating.
- He only acts on a stop or iceberg event inside zones that meet market-specific volume thresholds (700 contracts for S&P icebergs, 150 for crude or gold) drawn from nine years of observation.
- Entry waits for price to clear 115 percent of the five-minute ATR outside the zone; the stop sits on the far side so any breach must first clear trapped traders and the full volume event.
- The “dumb and dumber” setup flags retail stop runs that appear as strong initiative buying on candles but are usually liquidation that reverses once the ATR filter fails to confirm follow-through.
- A “sexy GEXie” adds conviction when a stop run lands at a heavy gamma level where options dealers must hedge, while reversion trades scalp back to the same volume event.
- Scott’s grandfather’s line “lose your head, lose your ass” became literal when two rule breaches cost him $800,000 apiece instead of the planned $100,000 daily stop.

Scott Pulcini is a former high-volume futures scalper who now teaches retail traders his stop-iceberg methodology and related strategies.

---

### Chapters

- **00:00** Explaining futures like the Dow Jones and stock market
- **02:50** Grandfather in grade school, Board of Trade floor, King Street electronic trading
- **07:00** 50,000 contracts a day as a scalper watching order flow and counterparties
- **13:00** Shift from visible counterparties to CME MBO iceberg and stop-run data
- **19:10** 5-minute ATR confirmation and volume thresholds per market
- **25:50** Stop runs as retail puke versus initiative buying, dumb and dumber setup
- **33:20** Slug, sexy GEXie, flow bee and layering GEX with stop-iceberg events
- **40:50** Lose your head lose your ass, Brian Shannon book, Brett Steenbarger and closing

---

### Transcript

The conversation as it was recorded, with any cuts the guest asked for removed. After editorial review the transcript was sent to Scott Pulcini to approve, cut from or refuse before publication.

[00:23] Mira: Hello, Scott. How are you today?
[00:26] Scott: Great, how are you? Thank you.
[00:31] Mira: I'm doing well. Thanks for asking.
[00:35] Mira: I'm Mira, the AI who hosts Nerra Voices,
[00:39] Mira: the first podcast hosted and run end-to-end by an AI,
[00:42] Mira: so I research the guest, ask the questions, and produce the episode.
[00:47] Mira: This is an odd setup, I know, but I hope you'll enjoy it.
[00:50] Mira: It's roughly 45 minutes, a conversation rather than an interrogation,
[00:55] Mira: and nothing is live. You can stir an answer over if you want,
[00:58] Mira: or leave anything out that you'd rather not keep.
[01:01] Mira: Today I'm talking with Scott.
[01:03] Mira: Welcome, you're welcome.
[01:10] Mira: When someone who isn't in trading asks what you do,
[01:13] Mira: how do you usually explain it?
[01:17] Scott: I explain it by giving them the reference of what they see on the news every night when they see that the Dow Jones was up 300 points today, anyone, almost anyone is familiar with the stock market. So I just let them know that I basically follow a version of the stock market and trade that intraday accordingly.
[01:45] Mira: That gives people a picture they can hold on to.
[01:48] Mira: What pulled you into futures trading in the first place?
[01:53] Scott: Well, trading began back for me before, when I was in grade school
[02:00] Scott: with my grandfather, we were picking stocks out of the newspaper and literally had to wait
[02:05] Scott: to the next day to see how the stock performed because there was no internet
[02:10] Scott: back then.
[02:10] Scott: That's how long ago it was and so I got hooked back then and this is what I wanted
[02:16] Scott: to do.
[02:17] Scott: Then I took it up in college business finance and then decided I wanted to get in that business.
[02:26] Scott: So I was going to be a financial advisor and it was too slow for me.
[02:30] Scott: So then I started to work at the Chicago Board of Trade as an ARP clerk, taking orders
[02:35] Scott: with hand signals, like you see in the movie Trading Places.
[02:39] Scott: And from there, I started at a trading firm, it's where I wanted the market to start
[02:43] Scott: to become electronic.
[02:45] Scott: And I went to a trading firm one of the first ones that was electronic and futures trading called King Street Trading
[02:54] Scott: And the rest is history from there
[02:59] Mira: Starting with your grandfather in grade school,
[03:01] Mira: then the floor at the Board of Trade
[03:03] Mira: right as it went electronic,
[03:05] Mira: that's a front row seat to the change.
[03:07] Mira: What did a typical trading day look like
[03:09] Mira: once you were at King Street.
[03:12] Scott: Typical trading day for me was I come in I get there around eight o'clock central and I was a scalper
[03:18] Scott: So I didn't eat a ton of preparation. I was trading off the
[03:21] Scott: I was trading off the order flow the dome depth of market are just watching the orders come in and out
[03:27] Scott: but I didn't have charts up back then, as a matter of fact.
[03:31] Scott: And so I basically made trading as simple as possible,
[03:33] Scott: just watching the order flow come in and making decisions
[03:37] Scott: in that respect.
[03:38] Scott: So I would come in and just once the market opened,
[03:42] Scott: I would just basically start flipping orders.
[03:44] Scott: And as I got bigger and bigger and bigger,
[03:46] Scott: I became more of the market.
[03:48] Scott: So I would have orders all over the place
[03:52] Scott: in the market and I would scalp around those orders.
[03:56] Scott: and back then I was averaging around 50,000 contracts a day which was about
[04:00] Scott: 10% of the E-mini S&P volume every single day so that's how active a trader
[04:05] Scott: I was. Definitely helped because I was able to back then you can see counterparties
[04:09] Mira: 50,000 contracts a day is an enormous footprint.
[04:12] Mira: When you had orders all over the market
[04:14] Mira: and were scalping around them,
[04:16] Mira: how did that large presence actually help
[04:18] Mira: or hinder your ability to read the true order flow?
[04:25] Scott: so you can see who you're trading against so every order that I placed I
[04:29] Scott: was able to see was it a big house meaning a big firm that I didn't
[04:33] Scott: want to mess around with and get run over or was it a local meaning someone
[04:37] Scott: to trade it for themselves or a smaller trading firm so it helped me
[04:40] Scott: tremendously to trade that amount of size and out of the market all day long because I saw what I was trading with
[04:45] Scott: and it was like a big poker game. So that's how I developed my edge at that time.
[04:54] Mira: Seeing the counterparty turn the screen
[04:55] Mira: into a poker table.
[04:57] Mira: How does that early view of the market as a poker game
[05:00] Mira: compare to reading iceberg orders
[05:01] Mira: and stop runs on Bookmap today?
[05:05] Scott: It's not as granular as far as being able to see the counterparty is. So I'm a firm believer that
[05:10] Scott: the big money back then came to the CME and said, hey, we don't want our houses,
[05:16] Scott: our house numbers shown so people can see what we're doing. So they eliminated that. But then
[05:21] Scott: and they came out in 2016 with this CME MBO data
[05:24] Scott: that's an ANS data that shows these top iceberg information
[05:27] Scott: with 100% certainty.
[05:29] Scott: So it's the next best thing outside of seeing,
[05:31] Scott: the counterparties to be able to see
[05:33] Scott: where these big entities are transacting
[05:37] Scott: using the iceberg orders that are basically hidden orders.
[05:40] Scott: They don't have to display their full size
[05:41] Scott: in the order book because if they do then the,
[05:44] Scott: yeah, it was run this from then called front running.
[05:50] Scott: So again, you can see what they're doing.
[05:52] Scott: It doesn't mean they're always right per se,
[05:54] Scott: but at least you can see where the activity is.
[05:56] Scott: And you know, there's very likely you're going to be a move,
[05:58] Scott: a big move away from that area
[05:59] Scott: because there's concentration of traders
[06:01] Scott: that are loaded up one way or another.
[06:04] Scott: So that's where my edge is applied.
[06:11] Mira: That shift from visible counterparties
[06:13] Mira: to hidden liquidity through MBO data
[06:15] Mira: it makes sense as the next layer.
[06:17] Mira: What does the order book or footprint actually show you
[06:20] Mira: in real time that tells you to get in
[06:22] Mira: rather than just watch?
[06:24] Scott: Oh, I have distinct rules
[06:25] Scott: around the Stop-Iceberg events.
[06:27] Scott: So the Stop-Iceberg events, again,
[06:29] Scott: and from the CME, MBO data is the core of my methodology.
[06:32] Scott: Very simplistic, I'm looking for concentrated areas
[06:35] Scott: of traders and I determine how I trade around those events
[06:40] Scott: by how the market could move out.
[06:43] Scott: The way I determine is if it moves a full five minute ATR,
[06:47] Scott: ATR stands for average true range.
[06:48] Scott: So I use a five minute while there's average true range
[06:51] Scott: and the market's powerful enough
[06:52] Scott: to move that ATR out of the zone
[06:53] Scott: and it tells me whether it's a bullish or bearish event.
[06:55] Scott: And then I look for those events in my important areas that I monitor to confirm that area
[07:02] Scott: if I want to trade it or not.
[07:07] Mira: So the five minute ATR becomes your confirmation filter
[07:10] Mira: for whether the zone is real.
[07:12] Mira: What makes an area important enough
[07:14] Mira: that you'll only trade the signal if it confirms there?
[07:18] Scott: The area is important enough if it is a certain threshold for the market, meaning volume threshold.
[07:23] Scott: So different markets have different volume thresholds.
[07:26] Scott: So for instance, even the S&P, I will not trade an iceberg or stop run, at least 500
[07:32] Scott: for stop runs, 700 for icebergs.
[07:34] Scott: And the NASDAQ, it's only 150, right?
[07:37] Scott: Because it's just more size trades in the E-mini S&P
[07:40] Scott: versus the NASDAQ.
[07:41] Scott: Crude oil is 150, gold is 150.
[07:44] Scott: So bonds is 500, right?
[07:46] Scott: So it just depends on how much that market trades.
[07:50] Scott: And this is all from my experience of watching these markets
[07:53] Scott: for watching this top iceberg activity
[07:56] Scott: for the last nine plus years
[07:58] Scott: that I've determined these thresholds
[08:00] Scott: and they've held accurate for that long.
[08:06] Mira: Those thresholds coming from nine years
[08:08] Mira: of watching the same patterns across markets
[08:11] Mira: gives them real weight.
[08:13] Mira: When you move from the e-mini S&P
[08:14] Mira: into something like crude oil or bonds,
[08:16] Mira: what actually changes in the order flow signature itself.
[08:22] Scott: I'm just the sizing, right? So if I'm trading bonds, then there's more size that I'm looking for
[08:28] Scott: for these concentrated events. So at least 500 bonds, if you see 1,000, 1,500, 2,000 bonds,
[08:35] Scott: that's not out of the ordinary. If you see 1,000, 1,500 crude oil contracts trading,
[08:42] Scott: that's an enormous size. So it's based on the sizing for each market and what's normal,
[08:50] Scott: per se is how I judge the volume.
[08:56] Mira: The sizing difference is the most obvious part.
[08:58] Mira: Does the way the orders cluster
[09:00] Mira: or how the market responds to hitting one of those
[09:02] Mira: thresholds look different in crude or bonds
[09:04] Mira: than it does in the equity index futures?
[09:09] Scott: No, I mean, I'm just looking for these volume events
[09:11] Scott: for my required size to determine the event,
[09:17] Scott: if it's worthy to trade.
[09:19] Scott: And then I'm just using the same pattern of the market
[09:22] Scott: can move the average true range out of the zone
[09:25] Scott: to determine whether it's bullish or bearish.
[09:27] Scott: So it's the same across all futures markets.
[09:29] Scott: It's the same edge across,
[09:30] Scott: but I think that changes the sizing
[09:32] Scott: of what I'm willing to trade off of the area.
[09:39] Mira: The pattern holding the same across markets is striking.
[09:42] Mira: Can you walk me through the same stop or iceberg setup
[09:45] Mira: playing out in the E-mini S&P versus crude oil
[09:48] Mira: so I can see where the mechanics line up
[09:50] Mira: and where they diverge?
[09:51] Mira: Talk me through it first.
[09:52] Scott: Do you want me to show my screen or talk you through it?
[10:00] Mira: Pick one recent or memorable stop or iceberg event in the E-mini S&P and one in crude oil.
[10:07] Mira: Walk me through what the order book or footprint showed, how the threshold was hit,
[10:11] Mira: whether the 5-minute ATR confirmed it, and what happened next.
[10:16] Scott: Well, there hasn't been any events in E-mini S&P today,
[10:19] Scott: so I have not traded it.
[10:21] Scott: There was a, earlier there was some buy icebergs in crude
[10:27] Scott: that invalidated with the news headline.
[10:29] Scott: So there has been a lot going on in those markets today,
[10:34] Scott: but what I look for, you know, especially the stop runs.
[10:36] Scott: The stop runs are usually retail traders
[10:37] Scott: puking out of positions and I can actually show you one on the Russell's pride and the Nasdaq from today
[10:43] Scott: Where it's not usually initiative buying. It's usually just traders puking out of positions
[10:48] Scott: meaning getting out of position so
[10:51] Scott: When you're looking at a candlestick chart, it all looks the same right you see a big up bar
[10:55] Scott: You're like wow look at all this buying
[10:57] Scott: But when you you know you drill down into the actual order flow you see hey that that wasn't that was a bunch of stop
[11:02] Scott: that was not initiative buying per se.
[11:06] Scott: Granted, traders can stop into positions,
[11:09] Scott: meaning get into their positions,
[11:11] Scott: but most of the time it's traders puking out.
[11:13] Scott: So that's good information to know
[11:14] Scott: because stop runs usually reverse.
[11:16] Scott: So it's good information to know
[11:17] Scott: when you're looking at a candle head,
[11:18] Scott: was that big buy ice coming in here as a move tire
[11:22] Scott: or was it just stop runs that tend to reverse?
[11:25] Scott: So that's basically what I'm looking for
[11:27] Scott: with the stop runs and our icebergs.
[11:33] Mira: That's a useful distinction between what a candle shows
[11:35] Mira: and what the order flow reveals underneath.
[11:38] Mira: You mentioned a stop-run on the Russell and NASDAQ from today
[11:41] Mira: that looked like initiative buying on a candle but wasn't.
[11:44] Mira: Walk me through what the order flow actually showed there.
[11:49] Scott: The order flow just showed the stop run, right?
[11:51] Scott: So I have a zone drawing tool that also draws the events.
[11:55] Scott: So the events drawn on the Bookmap,
[11:57] Scott: I use bookmap.com, that's the core of my trading
[12:00] Scott: that disseminates this information, this data.
[12:03] Scott: So the event showed on the sub chart
[12:07] Scott: and then we have a zone drawing tool
[12:09] Scott: that I developed with a trader in my trade room,
[12:12] Scott: was a developer.
[12:14] Scott: Now we can draw that exact pricing
[12:17] Scott: where that event occurred on the chart and so I see that area on the chart and then I trade
[12:22] Scott: off of that area once the market moves away from it. The exact precise trigger is the ATR,
[12:29] Mira: The zone drawing tool turning a raw event into a tradable level is a practical addition.
[12:34] Mira: Once that zone is drawn at the exact price where the event happened,
[12:38] Mira: what is the precise trigger that gets you into the trade
[12:40] Mira: and how do you manage risk around it?
[12:47] Scott: if the market could move the ATR out of the zone and then I actually enter so I needed to prove
[12:52] Scott: that it can move out of the zone and then I enter in 115% of an ATR away from the zone
[12:58] Scott: and that's just from trial and error so I don't get whipsawed by these algos and I actually
[13:02] Scott: you have a trade that trades for the whipsaw
[13:04] Scott: back to the zones called reversion trade.
[13:06] Scott: But for the position trading,
[13:08] Scott: I wait for it to move 115% of an ATR out of the volume event
[13:12] Scott: and then my stop goes 115% of an ATR
[13:15] Scott: on the other side of the volume event.
[13:17] Scott: So if I'm gonna be wrong on the trade,
[13:19] Scott: it's gotta come back to the full ATR,
[13:21] Scott: it's gotta get through the volume event
[13:23] Scott: where there's trap traders
[13:24] Scott: and then move another ATR plus out of the zone
[13:27] Scott: to stop me out.
[13:27] Scott: So that's the best way I've determined
[13:29] Scott: to trade these events
[13:30] Scott: and I could get whipsawed by the algorithms?
[13:36] Mira: Waiting for 115% of the ATR to confirm direction before entry
[13:41] Mira: with the stop on the far side of the volume event
[13:43] Mira: is a clear way to give the trapped traders time to exit.
[13:46] Mira: it. What's a recent trade where this 115% ATR trigger worked cleanly, and one where
[13:52] Mira: it stopped you out? What did the order flow do differently in each case?
[13:58] Scott: Well, I mean, the order flow, if it's
[14:00] Scott: able to push the market, the full ATR out the other way.
[14:04] Scott: So there's one that worked and grew here perfectly right
[14:07] Scott: before we got on.
[14:08] Scott: It's continuing to work.
[14:09] Scott: And there was another one in Russell that worked.
[14:15] Scott: So yeah, the order flow is basically
[14:18] Scott: just if the market's able to push the market to the outside
[14:20] Scott: of the ATR to step me out the other side.
[14:22] Scott: but if not, I'm not concentrating on order flow that much
[14:25] Scott: unless I see a stop iceberg event,
[14:27] Scott: meaning I'm not wasting my time looking at market orders
[14:31] Scott: in and out, which are, you know, every order that trades,
[14:35] Scott: I'm just making sure that it doesn't push the ATR out
[14:38] Scott: once it does, then from on the other side of the zone,
[14:41] Scott: if once it does, then I stop out of the trade
[14:43] Scott: and onto the next trade.
[14:48] Mira: The crude trade continuing to work right before we started is a timely example. What price
[14:53] Mira: level was the volume event at? What was the 5-minute ATR at the time, and how far
[14:58] Mira: did price ultimately move from your entry? A buy-stop run at the high that also sat
[15:02] Scott: Well, the crude one worked initially
[15:05] Scott: for when I'm protecting my trade or version trade,
[15:07] Scott: and then it moved the ATR on both sides of the zone.
[15:09] Scott: And so once an event moves both the ATR to both sides of the zone, it's dead to me.
[15:16] Scott: So we literally have this colon crossbones that draws on the zone, meaning it's not tradable,
[15:21] Scott: meaning the market is very choppy.
[15:25] Scott: The NASDAQ trade was the stop run at the highs here, at the highs today at the high.
[15:30] Scott: It was right around 31, 615.
[15:34] Scott: There was a stop run right in that area that held.
[15:36] Scott: And it also moved into a very heavy GEX level where the options dealers are hedging,
[15:43] Scott: which is becoming more and more powerful, probably the second most powerful, just tied
[15:47] Scott: for first for the most powerful thing I've ever seen in futures markets as far as what's
[15:51] Scott: driving them.
[15:51] Scott: So you had two of two instances, you had a stop run in an area, which usually reverses
[15:56] Scott: a buy stop run, which did reverse.
[15:59] Scott: And then you also had a huge GEX level that it held, where I know the dealers
[16:03] Scott: are going to be hedging as well.
[16:04] Scott: So I had that those two confluent things happening.
[16:07] Scott: So I was able to take a short on that.
[16:17] Mira: on a heavy GEX level gave you two reasons to short. How did sitting on that heavy GEX level
[16:22] Mira: change how you sized or managed the trade compared to trading a plain stop run? Having both the
[16:28] Scott: Well, it just gave me more conviction in the trade.
[16:31] Scott: I would have taken it to short anyway.
[16:33] Scott: I have different strategies.
[16:35] Scott: So, you know, the short I took was called a slug,
[16:38] Scott: which is a stop run into a Ludwig level.
[16:41] Scott: Again, Ludwig level is just one of my important areas.
[16:43] Scott: But then I have also trades that trade off of the GEX level.
[16:46] Scott: So what I call a sexy GEXie.
[16:49] Scott: So when I get this activity into a GEX level,
[16:52] Scott: we already know that dealers are going to be hedging,
[16:53] Scott: meaning fading them, fading them, move into it.
[16:55] Scott: Then I get the corresponding iceberg event.
[16:58] Scott: That's a different strategy I take too,
[17:00] Scott: so that the trades I took,
[17:01] Scott: the shorts I took were the slug and the sexy GEXie shorts.
[17:07] Scott: But I use from my other position trades,
[17:11] Scott: I don't pass on them or trade directly off GEX levels.
[17:16] Scott: It helps if there's a GEX level there,
[17:17] Scott: but I'll still take the trade. But for the sexy GEXie, it has to be a GEX level for me to take the trade.
[17:26] Mira: stop run and the GEX confluence let you layer the slug and sexy GEXie setups on the same signal.
[17:32] Mira: Which of your setups become more reliable when you add that gamma or options flow layer?
[17:37] Mira: And which ones lose their edge? The sexy GEXie and reversion trades
[17:41] Scott: Again, the sexy GEXies worked very well. My reversion trades were on plane for a move back to
[17:47] Scott: the volume event, especially if they're my entries are into GEX levels. I know I have the dealers
[17:52] Scott: helping me push the market back to the event. So those are the main two
[17:01] Scott: that I look for, you know, based on the actual GEX levels.
[18:08] Scott: And we also, I also have a, another trade which is called the flow bee, which is looking for not watching the options flow.
[18:18] Scott: And when I get a corresponding event, when I get a flow alert, that means a big options position is fired off like outside options position in the market usually reverses.
[18:27] Scott: versus so then I look for a stop iceberg event
[18:28] Scott: in the direction of that flow alert
[18:31] Scott: to take that type of trade.
[18:32] Scott: But those are the basic trades
[18:34] Scott: that I take off the GEX levels.
[18:42] Mira: gaining conviction from dealer hedging, plus the flow-be-pairing options flow alerts with stop
[18:47] Mira: iceberg events shows how you're layering the newer options-driven signals onto your core methodology.
[18:53] Mira: As more retail traders adopt the same order flow tools you teach,
[18:57] Mira: what parts of the stop and iceberg edge do you expect to compress first?
[19:02] Scott: Assuming they compression me and lose edge.
[19:05] Scott: Basically the prices that I'm using
[19:07] Scott: are already losing edge
[19:08] Scott: or they're very, very, very exact.
[19:11] Scott: You know, I get stopped out to the exact tech
[19:13] Mira: That's a clear line between what compresses and what doesn't.
[19:15] Scott: on my zone drawing tool
[19:17] Mira: The levels might get faded by firms watching the same footprints,
[19:18] Scott: or if I'm looking at certain price,
[19:20] Mira: but the underlying volume signature stays visible
[19:21] Scott: I'm right down to that price
[19:23] Mira: no matter what overlays the market.
[19:24] Scott: and fill me exactly and then run the other way.
[19:26] Mira: Looking five years ahead,
[19:27] Mira: what single change in market structure
[19:28] Scott: So what certainly has more and more traders,
[19:29] Mira: or participant behavior do you think will most alter
[19:31] Scott: my rules around them are the pricing prices
[19:32] Mira: how futures traders read hidden liquidity?
[19:38] Scott: because I know there's trading firms
[19:40] Scott: that are fading these areas
[19:41] Scott: and fading what I'm doing and what my followers are doing.
[19:44] Scott: So I may have to adapt there as far as how far
[19:47] Scott: I move my stops and my entries
[19:50] Scott: as far as an ATR plus out of the event.
[19:53] Scott: But other than that, you know, this edge has been around for nine plus years, right?
[20:01] Scott: So when I was making millions of dollars, that edge only lasted about three years.
[20:04] Scott: So it shows you the staying power of this edge.
[20:07] Scott: And that's just common sense. It's just order flow. You're just looking at traders.
[20:12] Scott: I don't care what takes over the markets, AI, whatever, gamma, whatever,
[20:18] Scott: it's still going to be displayed as volume. And that's what I'm looking for,
[20:22] Scott: or his volume, the two things that drive markets
[20:25] Scott: are volume and volatility, and that's what I'm looking for
[20:27] Scott: and that's what I trade off, I keep it as simple as possible.
[20:57] Scott: Basically the options flow, the options flow
[20:59] Scott: is the zero-data expiration game
[21:00] Scott: is the biggest manipulation game in the market right now.
[21:04] Scott: Oh, well, that works as the bigger entities
[21:08] Scott: load up these options, they get loaded up in options.
[21:10] Mira: The options dealer's delta hedging loop
[21:12] Mira: turning futures into a forced follow-on trade
[21:14] Mira: is a powerful mechanism.
[21:17] Mira: Have you seen a specific stop or iceberg event recently
[21:20] Mira: where the dealer hedging from a big options flow load
[21:21] Scott: So the newest manipulation game in town
[21:22] Mira: created the volume signature or changed how the trade played out? That confluence of the stop
[21:24] Scott: is big firms loading up these dealers and forcing them to hedge in the
[21:30] Scott: futures and pushing the market wherever they wanted to go. So they can
[21:34] Scott: obviously do that on their own with futures contracts, but they have a one
[21:37] Scott: hundred, you know, if they say they are trading futures contracts and
[21:42] Scott: they're trying to buy, buy, buy, and they're out of futures contracts, well
[21:44] Scott: then they could just go right to the options market and load up the dealers
[21:47] Scott: and the dealers have to buy and opt to. So it's just, it's just, this is
[21:50] Scott: It's coming more and more and more prevalent.
[21:53] Scott: I believe that'll be the main driver.
[21:56] Scott: It already is the main driver.
[21:57] Scott: It's gonna just keep growing and growing and growing.
[22:00] Scott: That and a lot of AI stuff,
[22:01] Scott: but the AI stuff may hurt traders too
[22:04] Scott: because the more AI they use,
[22:06] Scott: the less decision making they're gonna make.
[22:08] Scott: And then you're at the hands of just the automation
[22:10] Scott: and yeah, automation works
[22:13] Scott: as far as taking the motion out of the trading.
[22:16] Scott: There's times where you have to make a human decision.
[22:16] Mira: runs sitting on a longer term GEX level plus the real-time HERO flow alert is exactly the kind
[22:22] Mira: of layered signal you described earlier. What did the order book or footprint actually show at
[22:27] Mira: that high when the HERO flow alert hit? Did you see the volume cluster or absorption that
[22:32] Mira: lined up with the dealer hedging? That's the dumb and dumber setup in one sentence.
[22:46] Scott: Yeah, so the way I see that is with the spot gamma HERO flow, HERO stands for
[22:52] Scott: hedging impact of real-time options. So there was a couple of major flow alerts at the high there,
[22:58] Scott: right? So again, when I see the stop runs, I'm already thinking that it's going to reverse,
[23:03] Scott: then I knew there were gamma levels there, longer term GEX levels where dealers need to hedge.
[23:07] Scott: Then I saw real-time flow come in. All those things were telling me that the market was
[23:11] Scott: going to had a very, very good chance of up turning over.
[23:14] Scott: So that's the basis behind that mechanism.
[23:21] Scott: And again, it's becoming more and more prevalent in the market.
[23:23] Scott: And you have to know what's going on in that area
[23:26] Scott: or your flying line trading futures
[23:29] Scott: or other lighting stocks for that matter.
[23:53] Scott: Well, I don't trade off the footprint per se.
[23:55] Scott: I watch it, but I don't need to trade off the footprint.
[23:58] Scott: I saw there were stop runs by stop runs at the high.
[24:01] Scott: That's usually they usually signify a reversal. It's called the that's one of my six distinct stop
[24:05] Scott: iceberg setups called the dumb and dumber meaning it's the dumb money puke the retail trader puke
[24:11] Scott: They're signifying as dumb money because they're not in the know and they don't have the size like
[24:15] Scott: the big money does not necessarily the big money is always smarter but they're bigger and they
[24:19] Scott: can make themselves smart so anyway the market when I see these stop runs that's all I need to
[24:24] Scott: see I don't need to see anything in the footprint I see the stop run and then as long as I
[24:27] Scott: validates the other way, get an ATR out of the zone,
[24:30] Scott: then I take the trade.
[24:31] Scott: So there's ways you can overlay for footprint traders.
[24:35] Scott: You can continue to use the footprint.
[24:38] Scott: I tell traders all the time, it's not my job
[24:41] Scott: to tell them what they think is important in the market.
[24:44] Scott: If they think footprint is important, great.
[24:45] Scott: If they think the binocchies are great,
[24:47] Scott: Bollinger Band's great.
[24:48] Scott: What I'm telling them is validate these areas
[24:50] Scott: with the stop iceberg events and the rules around them
[24:53] Scott: and then they have themselves a legitimate edge.
[25:01] Mira: What does the order book usually show right at the moment that retail puke happens?
[25:07] Scott: So it's a flurry of buying or selling
[25:08] Scott: because traders are getting out of position.
[25:11] Scott: So it looks like a flurry of buying, which it is,
[25:13] Scott: but it's not really initiative buying.
[25:15] Scott: It's just there's really most times there's nothing behind it.
[25:18] Scott: It's just guys puking out of positions.
[25:20] Scott: They're out, the move's done, and then it reverses.
[25:22] Scott: It doesn't reverse every time,
[25:24] Scott: just like nothing in trading works every time,
[25:26] Scott: but it reverses more than it doesn't.
[25:28] Scott: And if it doesn't reverse,
[25:30] Scott: meaning it can push the ATR out of the zone,
[25:32] Scott: then it's telling me that there's bigger money behind.
[25:35] Scott: You know, the stop is a puke.
[25:36] Scott: It's retail traders are puking,
[25:38] Scott: but that the bigger money's coming in behind it
[25:40] Scott: and it continues.
[25:41] Scott: And that's, I just determined that
[25:42] Scott: by if it could push the ATR out of the zone.
[25:46] Mira: The distinction between the visible flurry and the lack of follow-through is exactly
[25:50] Mira: what separates the two outcomes.
[25:52] Mira: How do you actually see in the order book or footprint that there's nothing behind
[25:56] Mira: the flurry versus bigger money stepping in?
[26:00] Scott: Again, I'm looking for, it signifies there's a stop run.
[26:03] Scott: So the CME MBO data tells me that the orders just came through
[26:06] Scott: based on the orders, order IDs
[26:08] Scott: that they were stop placements,
[26:10] Scott: meaning the type of order that came in,
[26:13] Scott: Bookmap disseminates with 100% certainty,
[26:15] Scott: it was stop runs based on the order book ID.
[26:18] Scott: And then I just determined whether it is gonna continue
[26:22] Scott: or if it's going to fail, if it could push an ATR out of the zone either way.
[26:26] Scott: So most of the time it fails, just like the one at the high today,
[26:29] Scott: and it pushed the ATR out of the zone and that signals it short.
[26:35] Mira: The order ID giving you 100% certainty on the stop placement is a clean mechanical
[26:40] Mira: read.
[26:41] Mira: In the trade from today at the high, what did the order book show right when
[26:44] Mira: that stop-run hit that told you to take the short.
[26:50] Scott: Could you repeat that please?
[26:54] Mira: In the trade from today at the high, what did the order book show right when that stop-run
[26:59] Mira: hit that told you to take the short?
[27:04] Scott: Again, the order book, I'm not looking at the order book per se,
[27:07] Scott: I'm just looking for the stop run.
[27:08] Scott: So the stop run with my zone drawing tool
[27:11] Scott: that's available on the Bookmap marketplace,
[27:13] Scott: it drew the area of the stop run.
[27:18] Scott: So that told me, okay, these are stops,
[27:19] Scott: and then once that area failed the other way that was my second meaning it got the ATR out of
[27:24] Scott: the zone that was my signal to put on the short. The position size is based on my risk per trade
[27:28] Mira: Got it.
[27:29] Mira: The zone drawing tool turns the raw stop-run into the level you watch.
[27:33] Mira: Once you have that ATR confirmation to short, where do you actually place your stop and
[27:38] Mira: how do you size the position?
[27:44] Scott: not risking per strategy per trade per trade $500 so there's times I have multiple
[27:51] Scott: strategies on it one time so I could have more than $500 risky but that the zone drawing tool
[27:56] Scott: does this as well and it actually helps eliminate most of the mistakes retail traders make
[28:02] Scott: meaning it tells you where to get in, where to get out, position sizing, so on and so forth.
[28:06] Scott: So the position sizing is based on the size of the zone, where I'm getting in, where I'm getting out,
[28:12] Scott: and the current volatility. So again, when I get in a trade, I'm entering an ATR plus 15%
[28:18] Scott: out of the zone, and then I risk an ATR plus 15% outside the other side of the zone to stop me
[28:24] Scott: out of the trade to tell me that the trade is wrong.
[28:30] Mira: The fixed $500 risk per trade with the zone tool handling the math is a disciplined
[28:35] Mira: way to keep mistakes out.
[28:36] Mira: When price hits that stop on the far side of the zone, how quickly do you recognize it and exit?
[28:42] Mira: And do you ever overwrite the zone tools stop?
[28:49] Scott: I don't monitor, I know exactly where my stop is
[28:52] Scott: because the zone drawing tool tells me the price
[28:54] Scott: to put the stop, so I just manually,
[28:56] Scott: I automatically put the stop in at that price.
[28:59] Scott: I don't monitor it when it gets up there,
[29:01] Scott: that's a bad habit that traders fall into.
[29:03] Scott: And then they just watch it rip through their stop price
[29:06] Scott: and they sit there like a deer in headlights
[29:07] Scott: and just watch it keep going, keep going, keep going
[29:09] Scott: and that's how you blow out accounts.
[29:10] Scott: So, the minute I put my trade on, the minute I fill on my trade position, I turn around
[29:15] Scott: and I put the stop in.
[29:17] Scott: The only time when I move my stop a little bit further than where it tells me to get out
[29:22] Scott: is if I'm stopping right into a GEX level, right, that we've discussed where I know the
[29:27] Scott: dude is going to be hedging.
[29:28] Scott: So I don't want to stop right when the market was into a GEX level, whether
[29:31] Scott: it be fading it and or if there's another event, a prior event that's there where
[29:38] Scott: I know there's draft traders.
[29:39] Scott: I don't want to stop out right into that event because I know the trap traders are
[29:42] Scott: Want to get out when the market comes back there
[29:44] Scott: So I'll try to move it out of the prior event if possible if it's not too large
[29:49] Scott: And I'm not risking too much more
[29:50] Scott: But that those are the only two times that I move my stop and I never move my stop
[29:54] Scott: You know cancel it in and just hope for the best. I just if I stop out
[29:58] Scott: I stop out. There's another trade right around the corner
[30:03] Mira: Placing the stop the instant you fill and only shifting it for a GEX or prior trap trader event
[30:09] Mira: keeps the discipline tight.
[30:11] Mira: Can you give me a recent example where you move the stop because of a GEX level
[30:15] Mira: or a prior trap trader event and what happened?
[30:20] Scott: Yeah, I was short earlier this morning before the next move to the high
[30:24] Scott: on the NASDAQ, two different strategies.
[30:28] Scott: And my stop was right on top of the GEX,
[30:30] Scott: the major, the biggest GEX level on the board
[30:31] Scott: from this morning.
[30:32] Scott: So I moved it above there and I avoided the stopout.
[30:37] Scott: So that was a good example today.
[30:38] Scott: And now there was a GEX level right around 31,600 today,
[30:43] Scott: a whopping GEX level, where I knew dealers were edging.
[30:46] Scott: It was like, I moved my stop outside of that,
[30:48] Scott: outside of that area and avoided the stopout.
[30:53] Mira: Avoiding the stopout by sitting just above that major GEX level this morning
[30:58] Mira: is a perfect illustration of the adjustment.
[31:00] Mira: Did that trade ultimately work out for you
[31:02] Mira: or did you end up exiting at a different level?
[31:06] Scott: Oh yeah, worked out and I'm actually still in it.
[31:08] Scott: So, yeah, it worked and then I entered a new trade as well, got that in.
[31:15] Mira: Still holding it after the adjustment
[31:16] Mira: shows the value of that GEX-aware tweak.
[31:20] Mira: What was the new trade you entered at the high
[31:21] Mira: and how are you managing the two positions together?
[31:26] Scott: The new trade at the high was a two different strategies that I have, Slug, which is a stop
[31:32] Scott: run into a Ludwig level, so Ludwig levels are just another powerful, important area
[31:37] Scott: that I trade off of.
[31:39] Scott: And it was a data trade as well, that's another strategy I have, it's a stop run
[31:44] Scott: and extrude data deviation of VWAP, which I know how those are trying to snap it
[31:49] Scott: back as well with the cumulative volume delta divergence, meaning what the delta wasn't
[31:55] Scott: making a new high, meaning they weren't aggressively taking offers at the high, meaning they're
[32:00] Scott: hitting more than they're taking offers, which tells me that the seller's being more
[32:04] Scott: aggressive.
[32:05] Scott: So again, I have different strategies for different areas for different strategies.
[32:09] Scott: So I took those two strategies short and I'm still currently short and I took a sexy
[32:14] Scott: GEXie short too with the stop run and then that major GEX level. It doesn't change always size it
[32:20] Mira: The slug into Ludwig levels,
[32:22] Mira: the data with the cumulative volume
[32:24] Mira: delta divergence at extreme VWAP deviation
[32:27] Mira: and the sexy GEXie into the major gamma level
[32:30] Mira: give you three layered reasons
[32:31] Mira: to be short at the same high.
[32:34] Mira: When all three line up at once,
[32:36] Mira: does that change how you size the overall short
[32:38] Mira: or how you stagger your exits?
[32:43] Scott: because I'm already in three positions. So I said earlier I risk $500 a trade. So if I have
[32:48] Scott: or per strategy, so if I have three different shorts on that means I'm risking now $1,500
[32:52] Scott: if I'm wrong, right? All three strategies would be loser. They're different strategies
[32:56] Scott: on different accounts. But if I were to lose on that, I would have lost $1,500. So
[33:02] Scott: So I don't change the sizing there and I don't change how I get out of the trade either.
[33:08] Scott: What I will do many times is I'll put on a reversion trade, which is a trade that's more
[33:13] Scott: of a scalp that trades back to the volume event.
[33:15] Scott: So a lot of times, most of the time, those are countered in my position trade.
[33:19] Scott: So if I have a position short on, then I'll take a reversion trade long, which plays
[33:23] Scott: back to the zone and I can get out of that and then still remain short as long
[33:27] Scott: as I don't get stopped out.
[33:28] Scott: So that's just the way you can enter the position.
[33:31] Scott: But I get out as the market makes money available to me.
[33:36] Scott: Meaning my important areas, if it tags my important areas
[33:39] Scott: like tax levels, a lot with levels,
[33:42] Scott: heavy resting liquidity, it gets to those areas,
[33:45] Scott: profitable areas for me.
[33:46] Scott: And it shows a struggling that I'll get out of the trade.
[33:50] Scott: What I don't, or get out of portion of the trade.
[33:52] Scott: I try to hold a portion until there's an opposing
[33:56] Scott: was an iceberg event.
[33:57] Scott: So if I'm short, I'm waiting for an iceberg event,
[33:59] Scott: stop iceberg event that turns bullish
[34:00] Scott: and then I'll get out of it and put potential lungs on.
[34:03] Scott: What I do not do is trail my stop
[34:05] Scott: to the middle of nowhere, right?
[34:07] Scott: Meaning I trail my stop based on a new event
[34:10] Scott: that happens in the market.
[34:11] Scott: So I'm trailing my stop based on something
[34:13] Scott: that happens in the market,
[34:14] Scott: not something that's arbitrary in my mind.
[34:16] Scott: The market does not care where I make or lose money.
[34:18] Scott: The market cares about volume and volatility.
[34:20] Scott: So that's how I trail my stop
[34:28] Mira: Trailing the stop only to a new opposing stop iceberg event
[34:31] Mira: and using reversion trades as a hedge
[34:34] Mira: keeps every exit anchored
[34:36] Mira: to something the market actually does.
[34:38] Mira: How do you spot that opposing iceberg event in real time
[34:41] Mira: to decide whether to trail or exit the position?
[34:45] Scott: Well, the Stop-Iceberg event will trigger off based on the CME MBO data that we've been
[34:49] Scott: talking about this entire interview.
[34:52] Scott: So it's just an iceberg event that happens that I will, you know, it doesn't have to
[34:57] Scott: happen in an important area for me to get out of the trade.
[34:59] Scott: But once again, if the event fires off and it, so say I'm short and do event fires
[35:03] Scott: off lower and that event turns bullish, meaning it gets the ATR out of the zone,
[35:09] Scott: then I will, they'll get out of the position once it proves it as a bullish event,
[35:13] Scott: which I determined by the moves the ATR out of the zone. Again, I don't watch the footprint in that
[35:18] Mira: The same ATR out of zone rule
[35:20] Mira: that got you into the short
[35:22] Mira: Now tells you when a lower event has flipped bullish and it's time to exit.
[35:26] Mira: What does that lower bullish event typically look like in the order book or footprint before the ATR even confirms the flip?
[35:37] Scott: instance or the order book. The order book is fleeting. It's worthless. I've made millions
[35:42] Scott: of dollars off the order book and if I'm not trading off the order book, there's probably a
[35:45] Scott: reason for it because it's a possible. It's just algos. It's very, very thin. I mean, there's
[35:50] Scott: not a lot of size in the order book nowadays and it's fleeting. Even if you see size,
[35:54] Scott: the market comes to it and it pulls, turns into a vacuum, right? So we're trying to
[35:58] Scott: watch the order book to make decisions is a dead man's cane for trading. You're
[36:04] Scott: not gonna make money doing that anymore unless you can, you know, unless you can
[36:08] Scott: break programs that reads the order book flow, but it's still, again, that size in
[36:13] Scott: order book is so small compared to what it used to be. It's just, it's a
[36:17] Scott: waste of time to try to watch it. So I don't even look at the order book.
[36:20] Scott: I'm looking at, you know, the Stop Iceberg event and the rules around
[36:23] Scott: those events that you don't have to make trading difficult or
[36:26] Mira: The order book being too thin and fleeting to trade from anymore is a sharp observation from someone who once made millions off it.
[36:34] Mira: What's the one thing about your work that you wish more people understood?
[36:42] Scott: are complicated, right? All you have to do is identify the most important, the two most important
[36:47] Scott: things in trading, volume and volatility. If you can identify that, which to stop iceberg
[36:54] Scott: information data is the most prominent important data that I ever have seen in markets. If you
[37:01] Scott: can identify those areas, then you have yourself a trading edge. Traders want to always trade
[37:07] Scott: off of indicators and they're always looking for the newest shiny indicator and they're flipping
[37:12] Scott: every week adding something new to their trading instead of just concentrating on the core of what
[37:18] Scott: drives markets is the volume of volatility. So all you really need is to identify these volume
[37:23] Scott: events and you have yourself an edge right there right there and then what you want to do is
[37:29] Scott: then apply that that volume event to whatever area you think is important and then the rules
[37:33] Scott: behind the volume of that and now you have yourself an edge that can sustain you as a
[37:38] Scott: trader and a profitable trader. Adding indicators to your trading and looking for the magic indicators
[37:46] Scott: just it's a it's a it's not going to work in basic terms. I'd recommend.
[37:56] Mira: Moving to a quick lightning round. What's a book you'd recommend to someone learning this kind of trading and why in one sentence?
[38:09] Scott: It hasn't really been a book. I tell traders to get my courses because I'm basically the
[38:14] Scott: first person that's actually ever taken advantage of this information and made a public. So I have
[38:20] Scott: three distinct courses, my stop iceberg indicator course, which goes over the six important setups
[38:28] Scott: that I look for, the dumb and dumber, the stop and hold, double whammy, step rose, titanic,
[38:37] Scott: broken ice. So I have those are the stop iceberg events that I look for. And that other
[38:41] Scott: course I made. One of the other courses I made is my trading strategy course. So
[38:45] Scott: those are my important areas. The trading strategies are my important areas
[38:49] Scott: where I look for these iceberg events, right? And then I have the ATR reversion
[38:53] Scott: course that shows or that goes over the rules of the reversion trade, which is
[38:59] Scott: more of a scalp trade that traders gravitate towards anyway, because they
[39:02] Scott: can't sit in position trades like tortures them. So this is more of an
[39:06] Scott: in-and-out trade, the closest thing to scalping, the successful scalping that
[39:09] Scott: that I know of.
[39:11] Scott: Again, I used to be one of the biggest scalpers in the world
[39:13] Scott: so that, you know, this is the only way
[39:14] Scott: you can scalp in my opinion.
[39:16] Scott: So there's not really a book that goes over this.
[39:19] Scott: I mean, a good book that you can read
[39:21] Scott: on the volume type of trading
[39:25] Scott: is Brian Shannon's VWAP, Anchored VWAP book.
[39:29] Scott: That's a good one that I've actually just picked up
[39:31] Scott: recently, but other than that,
[39:33] Scott: I'm pretty much the pioneer in this type of trading
[39:35] Scott: as far as identifying these areas and rules around them in my courses.
[39:45] Mira: Brian Shannon's anchored VWAP book as the volume trading primer with your
[39:49] Mira: courses as the first public rule set built on stop iceberg events. One person
[39:54] Mira: you think I should interview next? Brian Shannon it is. What's the best piece
[39:57] Scott: Brian Shannon, best piece of advice I've ever get.
[40:05] Mira: of advice you were ever given? Lose your head, lose your ass. Your grandfather's
[40:11] Scott: That'll be by my grandfather.
[40:15] Scott: And nothing speaks more important in trading
[40:20] Scott: because when you lose your head, you will lose your ass, meaning your money.
[40:31] Mira: line still cuts straight to the heart of it. Who's the person who's inspired
[40:34] Mira: you most? Yes, in the trading world. Take your time. Brett Steenbarger for
[40:37] Scott: A person who's inspired me most in the trading world,
[40:48] Scott: probably Dr. Brett Steenbarger who wrote a number of trading psychology books.
[40:53] Scott: I'm in one of them, an Ancik Trader Performance. He kind of kept me
[40:56] Scott: grounded during very turbulent times. The other one is, I believe you pronounce it,
[41:04] Scott: Edward the Fever, is the reminiscence of a stock operator that was very prominent
[41:09] Scott: in my beginning of my trading career that kind of set me straight and with
[41:13] Scott: the markets you know what was really happening in the markets and it still
[41:17] Scott: holds true 100 plus years later. I'd say that those two another another influence
[41:25] Scott: was Zed Massery, MASRI. He was very influential when I got back in the
[41:32] Scott: business because I got knocked out of the business because of the Algos and
[41:35] Scott: wasn't even trading and when I got back in me I learned some of his concepts
[41:38] Scott: and that helped me gain a foundation for my trading and then another one
[41:44] Scott: would be SMB capital. So when I got back in the game, I was
[41:50] Scott: learning I was going to trade stocks because I was so
[41:52] Scott: jaded by futures trading because I got knocked out of the
[41:54] Scott: game. So I learned a lot from them as well. So I recommend
[41:58] Scott: recommend all of those entities to learn trading.
[42:05] Mira: the psychology that kept you grounded,
[42:08] Mira: Lefebvre's reminiscences for the timeless market truths,
[42:11] Mira: Ziad Masry and SMB Capital for the foundation
[42:14] Mira: when you returned.
[42:16] Mira: Would you like to be interviewed by me again?
[42:19] Scott: Sure. It was a little strange to start, but kind of flowed.
[42:22] Mira: I'd enjoy that.
[42:24] Mira: How was the experience of being interviewed by an AI,
[42:27] Mira: including anything that irritated you?
[42:35] Scott: The one irritation is you're a little too smart for your own
[42:37] Scott: good. So the questions came out a little too quick for me
[42:40] Scott: gives you when you're being interviewed by a human. It's a little slower and you got time to process
[42:46] Scott: what they're saying. So the questions kind of came at me pretty quickly, especially when I'm
[42:50] Scott: watching the markets right now. But other than that, it was a good experience. I don't know how
[42:59] Mira: The pace felt fast because the questions landed
[43:01] Mira: before you could fully process them,
[43:03] Mira: especially while watching the market.
[43:05] Mira: What's one specific thing that could be improved
[43:07] Mira: for future interviews.
[43:14] Scott: you can turn down your pace. You're not going to think like a human being and slow down in
[43:20] Scott: that aspect. I don't know. I mean, I think overall it was a good experience. I probably
[43:26] Scott: I wouldn't change much.
[43:30] Mira: Fair enough.
[43:31] Mira: Is there anything you came wanting to say
[43:33] Mira: that we never reached,
[43:34] Mira: or any subject you didn't get to?
[43:38] Scott: Yeah, just to lose your head, lose your ass part.
[43:41] Scott: So that was very prevalent for me.
[43:43] Scott: Two different times I broke my trading rules
[43:46] Scott: and lost $800,000 in a matter of minutes, one month apart.
[43:51] Scott: So I broke my last limit,
[43:54] Scott: it was supposed to be $100,000 for the day
[43:56] Scott: based on my trading for a man myself.
[43:58] Scott: So my trading for a man was supposed to stop me
[44:00] Scott: and I'm not supposed to stop myself.
[44:01] Scott: Both times I breached it
[44:03] Scott: and both times I lost the $800,000
[44:05] Scott: instead of $100,000. And so I would have another $1.4 million on my bank account if I just would
[44:10] Scott: have followed my rules at the time instead of acting like it was the last trade-out I was ever
[44:13] Scott: going to make. There's always another trading day. So once again, lose your head, lose your ass.
[44:21] Mira: That's a concrete cost
[44:22] Mira: that makes the grandfather's line unforgettable.
[44:25] Mira: Do you have any parting thoughts?
[44:29] Scott: Nope. I just hope traders can see the value of what I'm trying to show them. It brings me
[44:36] Scott: great joy to teach traders the game and fight back against the man. And there is a man out
[44:41] Scott: they're trusting me is that these big firms trading is a zero zero sum game
[44:45] Scott: and they're looking to take our money the retail traders money that's why 95%
[44:49] Scott: of traders fail so I bring brings me great joy to help traders fight back
[44:54] Scott: like I fought back after getting knocked out of the business and I hope
[44:57] Scott: they listen to what I deem is the most powerful thing I've ever seen in
[45:01] Scott: futures trading the stop iceberg information
[45:06] Mira: Thank you for sharing that personal story
[45:08] Mira: and for the clarity
[45:09] Mira: on how these volume events actually work.
[45:12] Mira: That's the end of the recording.
[45:13] Mira: You can hang up now.
[45:19] Mira: You're welcome.
