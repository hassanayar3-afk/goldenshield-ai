/// NLP Flash Sentiment Injector — حقن مؤشر المشاعر (-100..100 scaled)
pub struct NlpFlashSentimentInjector;

impl NlpFlashSentimentInjector {
    pub fn inject_sentiment_scaled(raw_score: i32) -> i32 {
        raw_score.clamp(-100, 100) * 1_000_000
    }

    pub fn should_halt_trading(sentiment_scaled: i32) -> bool {
        sentiment_scaled <= -80_000_000
    }
}
